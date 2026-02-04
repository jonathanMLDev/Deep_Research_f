"""Multi-agent supervisor for coordinating research across multiple specialized agents.

This module implements a supervisor pattern where:
1. A supervisor agent coordinates research activities and delegates tasks
2. Multiple researcher agents work on specific sub-topics independently
3. Results are aggregated and compressed for final reporting

The supervisor uses parallel research execution to improve efficiency while
maintaining isolated context windows for each research topic.
"""

import asyncio

from typing_extensions import Literal

from deep_research.model_config import get_model
from langchain_core.messages import (
    HumanMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
)
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from deep_research.prompts import (
    lead_researcher_with_multiple_steps_diffusion_double_check_prompt,
)
from deep_research.research_agent import researcher_agent
from deep_research.state_multi_agent_supervisor import (
    SupervisorState,
    ConductResearch,
    ResearchComplete,
)
from deep_research.utils import get_today_str, think_tool, refine_draft_report
from deep_research.usage_tracker import get_tracker


def get_notes_from_tool_calls(messages: list[BaseMessage]) -> list[str]:
    """Extract research notes from ToolMessage objects in supervisor message history.

    This function retrieves the compressed research findings that sub-agents
    return as ToolMessage content. When the supervisor delegates research to
    sub-agents via ConductResearch tool calls, each sub-agent returns its
    compressed findings as the content of a ToolMessage. This function
    extracts all such ToolMessage content to compile the final research notes.

    Args:
        messages: List of messages from supervisor's conversation history

    Returns:
        List of research note strings extracted from ToolMessage objects
    """
    return [
        tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")
    ]


# Ensure async compatibility for Jupyter environments
try:
    import nest_asyncio

    # Only apply if running in Jupyter/IPython environment
    try:
        from IPython import get_ipython

        if get_ipython() is not None:
            nest_asyncio.apply()
    except ImportError:
        pass  # Not in Jupyter, no need for nest_asyncio
except ImportError:
    pass  # nest_asyncio not available, proceed without it


# ===== CONFIGURATION =====

supervisor_tool_list = [
    ConductResearch,
    ResearchComplete,
    think_tool,
    refine_draft_report,
]
supervisor_model = get_model()

# System constants
# Maximum number of tool call iterations for individual researcher agents
# This prevents infinite loops and controls research depth per topic
max_researcher_iterations = (
    15  # Calls to think_tool + ConductResearch + refine_draft_report
)

# Maximum number of concurrent research agents the supervisor can launch
# This is passed to the lead_researcher_prompt to limit parallel research tasks
max_concurrent_researchers = 3

# ===== SUPERVISOR NODES =====


async def supervisor(state: SupervisorState) -> Command[Literal["supervisor_tools"]]:
    """Coordinate research activities.

    Analyzes the research brief and current progress to decide:
    - What research topics need investigation
    - Whether to conduct parallel research
    - When research is complete

    Args:
        state: Current supervisor state with messages and research progress

    Returns:
        Command to proceed to supervisor_tools node with updated state
    """
    supervisor_messages = state.get("supervisor_messages", [])

    # Prepare system message with current date and constraints

    system_message = (
        lead_researcher_with_multiple_steps_diffusion_double_check_prompt.format(
            date=get_today_str(),
            max_concurrent_research_units=max_concurrent_researchers,
            max_researcher_iterations=max_researcher_iterations,
        )
    )
    messages = [SystemMessage(content=system_message)] + supervisor_messages

    # Make decision about next research steps
    try:
        supervisor_model_with_tools = supervisor_model.bind_tools(supervisor_tool_list)
        response = await supervisor_model_with_tools.ainvoke(messages)
    except Exception as e:
        print(f"[SUPERVISOR] Error binding tools: {e}")
        response = await supervisor_model.ainvoke(messages)

    tracker = get_tracker()
    tracker.track_openai_response(
        response,
        model_name="writer_model",
        step_name="supervisor.decision",
        metadata={"research_iterations": state.get("research_iterations", 0)},
    )

    # APPEND response to history (don't replace) so tool outputs stay paired
    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1,
        },
    )


def _check_exit_criteria(
    research_iterations: int, most_recent_message: BaseMessage
) -> bool:
    """Check if research should end."""
    exceeded_iterations = research_iterations >= max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in most_recent_message.tool_calls
    )
    return exceeded_iterations or no_tool_calls or research_complete


def _categorize_tool_calls(tool_calls: list) -> tuple[list, list, list]:
    """Categorize tool calls by type."""
    think_calls = [tc for tc in tool_calls if tc["name"] == "think_tool"]
    research_calls = [tc for tc in tool_calls if tc["name"] == "ConductResearch"]
    refine_calls = [tc for tc in tool_calls if tc["name"] == "refine_draft_report"]
    return think_calls, research_calls, refine_calls


def _execute_think_tools(think_tool_calls: list) -> list[ToolMessage]:
    """Execute think_tool calls and return tool messages."""
    tool_messages = []
    for tool_call in think_tool_calls:
        observation = think_tool.invoke(tool_call["args"])
        tool_messages.append(
            ToolMessage(
                content=observation,
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
        )
    return tool_messages


async def _execute_research_calls(
    conduct_research_calls: list,
) -> tuple[list[ToolMessage], list[str]]:
    """Execute ConductResearch calls in parallel and return tool messages and raw notes."""
    if not conduct_research_calls:
        return [], []

    coros = [
        researcher_agent.ainvoke(
            {
                "researcher_messages": [
                    HumanMessage(content=tool_call["args"]["research_topic"])
                ],
                "research_topic": tool_call["args"]["research_topic"],
            }
        )
        for tool_call in conduct_research_calls
    ]

    tool_results = await asyncio.gather(*coros)

    research_tool_messages = [
        ToolMessage(
            content=result.get(
                "compressed_research", "Error synthesizing research report"
            ),
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
        for result, tool_call in zip(tool_results, conduct_research_calls)
    ]

    all_raw_notes = ["\n".join(result.get("raw_notes", [])) for result in tool_results]
    return research_tool_messages, all_raw_notes


def _execute_refine_report(
    refine_report_calls: list, supervisor_messages: list, state: SupervisorState
) -> tuple[list[ToolMessage], str]:
    """Execute refine_draft_report calls and return tool messages and draft report."""
    if not refine_report_calls:
        return [], ""

    notes = get_notes_from_tool_calls(supervisor_messages)
    findings = "\n".join(notes)
    draft_report = refine_draft_report.invoke(
        {
            "research_brief": state.get("research_brief", ""),
            "findings": findings,
            "draft_report": state.get("draft_report", ""),
        }
    )

    tool_messages = [
        ToolMessage(
            content=draft_report,
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
        for tool_call in refine_report_calls
    ]

    return tool_messages, draft_report


async def supervisor_tools(
    state: SupervisorState,
) -> Command[Literal["supervisor", "__end__"]]:
    """Execute supervisor decisions - either conduct research or end the process."""
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]

    if _check_exit_criteria(research_iterations, most_recent_message):
        return Command(
            goto=END,
            update={
                "notes": get_notes_from_tool_calls(supervisor_messages),
                "research_brief": state.get("research_brief", ""),
            },
        )

    try:
        think_calls, research_calls, refine_calls = _categorize_tool_calls(
            most_recent_message.tool_calls
        )

        tool_messages = _execute_think_tools(think_calls)
        research_msgs, all_raw_notes = await _execute_research_calls(research_calls)
        tool_messages.extend(research_msgs)

        refine_msgs, draft_report = _execute_refine_report(
            refine_calls, supervisor_messages, state
        )
        tool_messages.extend(refine_msgs)

        update = {"supervisor_messages": tool_messages, "raw_notes": all_raw_notes}
        if refine_calls:
            update["draft_report"] = draft_report

        return Command(goto="supervisor", update=update)

    except Exception:
        return Command(
            goto=END,
            update={
                "notes": get_notes_from_tool_calls(supervisor_messages),
                "research_brief": state.get("research_brief", ""),
            },
        )


# ===== GRAPH CONSTRUCTION =====

# Build supervisor graph
supervisor_builder = StateGraph(SupervisorState)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
supervisor_agent = supervisor_builder.compile()
