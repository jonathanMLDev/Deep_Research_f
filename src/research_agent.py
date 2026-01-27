"""Research Agent Implementation.

This module implements a research agent that can perform iterative web searches
and synthesis to answer complex research questions.
"""

import os
from typing_extensions import Literal

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
    filter_messages,
)
from deep_research.model_config import get_model, get_light_model

from deep_research.state_research import ResearcherState, ResearcherOutputState
from deep_research.utils import tavily_search, get_today_str, think_tool
from deep_research.prompts import (
    research_agent_prompt,
    compress_research_system_prompt,
    compress_research_human_message,
)
from deep_research.usage_tracker import get_tracker
from deep_research.run_logger import get_logger

# ===== CONFIGURATION =====

# Maximum number of Tavily searches per researcher agent
# Can be overridden via MAX_TAVILY_SEARCHES environment variable
MAX_TAVILY_SEARCHES = int(os.getenv("MAX_TAVILY_SEARCHES", "5"))

# Set up tools and model binding
tools = [tavily_search, think_tool]
tools_by_name = {tool.name: tool for tool in tools}

# Initialize models
model = get_model()
model_with_tools = model.bind_tools(tools)

compress_model = get_light_model()

# ===== AGENT NODES =====


def llm_call(state: ResearcherState):
    """Analyze current state and decide on next actions.

    The model analyzes the current conversation state and decides whether to:
    1. Call search tools to gather more information
    2. Provide a final answer based on gathered information

    Returns updated state with the model's response.
    """
    # Format prompt with current date and search limit
    formatted_prompt = research_agent_prompt.format(
        date=get_today_str(), max_searches=MAX_TAVILY_SEARCHES
    )
    response = model_with_tools.invoke(
        [SystemMessage(content=formatted_prompt)] + state["researcher_messages"]
    )

    tracker = get_tracker()
    tracker.track_openai_response(
        response,
        model_name="writer_model",
        step_name="research_agent.llm_call",
        metadata={"tool_calls": bool(response.tool_calls)},
    )

    return {"researcher_messages": [response]}


def tool_node(state: ResearcherState):
    """Execute all tool calls from the previous LLM response.

    Executes all tool calls from the previous LLM responses with Tavily search limit enforcement.
    Returns updated state with tool execution results.
    """
    last_message = state["researcher_messages"][-1]
    tool_calls = last_message.tool_calls or []
    tavily_search_count = state.get("tavily_search_count", 0)

    # Execute tool calls with limit enforcement
    observations = []
    skipped_searches = 0

    for tool_call in tool_calls:
        tool_name = tool_call["name"]

        # Check and enforce Tavily search limit
        if tool_name == "tavily_search":
            if tavily_search_count >= MAX_TAVILY_SEARCHES:
                limit_message = (
                    f"⚠️ Tavily search limit ({MAX_TAVILY_SEARCHES}) reached. "
                    f"This search has been skipped. Please proceed with the information "
                    f"gathered from previous searches ({tavily_search_count} searches completed)."
                )
                observations.append(limit_message)
                skipped_searches += 1

                # Log limit reached
                try:
                    logger = get_logger()
                    logger.log_step(
                        "research_agent.tavily_limit",
                        f"Tavily search limit reached ({MAX_TAVILY_SEARCHES})",
                        extra={
                            "current_count": tavily_search_count,
                            "limit": MAX_TAVILY_SEARCHES,
                            "research_topic": state.get("research_topic", "unknown"),
                        },
                    )
                except Exception:
                    pass
                continue

            # Increment counter before executing search
            tavily_search_count += 1

        # Execute the tool
        tool = tools_by_name[tool_name]
        observations.append(tool.invoke(tool_call["args"]))

    # Create tool message outputs
    tool_outputs = [
        ToolMessage(
            content=observation, name=tool_call["name"], tool_call_id=tool_call["id"]
        )
        for observation, tool_call in zip(observations, tool_calls)
    ]

    return {
        "researcher_messages": tool_outputs,
        "tavily_search_count": tavily_search_count,
    }


def compress_research(state: ResearcherState) -> dict:
    """Compress research findings into a concise summary.

    Takes all the research messages and tool outputs and creates
    a compressed summary suitable for the supervisor's decision-making.
    """

    system_message = compress_research_system_prompt.format(date=get_today_str())
    research_topic = state.get("research_topic", "the research topic")
    human_message_content = compress_research_human_message.format(
        research_topic=research_topic
    )
    messages = [SystemMessage(content=system_message)] + state.get(
        "researcher_messages", []
    )
    messages += [HumanMessage(content=human_message_content)]
    response = compress_model.invoke(messages)

    tracker = get_tracker()
    tracker.track_openai_response(
        response,
        model_name="summarization_model",
        step_name="research_agent.compress_research",
        metadata={"research_topic": research_topic},
    )

    # Extract raw notes from tool and AI messages
    raw_notes = [
        str(m.content)
        for m in filter_messages(
            state["researcher_messages"], include_types=["tool", "ai"]
        )
    ]

    return {
        "compressed_research": str(response.content),
        "raw_notes": ["\n".join(raw_notes)],
    }


# ===== ROUTING LOGIC =====


def should_continue(
    state: ResearcherState,
) -> Literal["tool_node", "compress_research"]:
    """Determine whether to continue research or provide final answer.

    Determines whether the agent should continue the research loop or provide
    a final answer based on whether the LLM made tool calls.

    Returns:
        "tool_node": Continue to tool execution
        "compress_research": Stop and compress research
    """
    messages = state["researcher_messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, continue to tool execution
    if last_message.tool_calls:
        return "tool_node"
    # Otherwise, we have a final answer
    return "compress_research"


# ===== GRAPH CONSTRUCTION =====

# Build the agent workflow
agent_builder = StateGraph(ResearcherState, output_schema=ResearcherOutputState)

# Add nodes to the graph
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("compress_research", compress_research)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node",  # Continue research loop
        "compress_research": "compress_research",  # Provide final answer
    },
)
agent_builder.add_edge("tool_node", "llm_call")  # Loop back for more research
agent_builder.add_edge("compress_research", END)

# Compile the agent
researcher_agent = agent_builder.compile()
