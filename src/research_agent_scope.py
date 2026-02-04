"""User Clarification and Research Brief Generation.

This module implements the scoping phase of the research workflow, where we:
1. Assess if the user's request needs clarification
2. Generate a detailed research brief from the conversation

The workflow uses structured output to make deterministic decisions about
whether sufficient context exists to proceed with research.
"""

import os
from datetime import datetime
from typing_extensions import Literal

from deep_research.model_config import get_model
from langchain_core.messages import HumanMessage, get_buffer_string
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from deep_research.prompts import (
    transform_messages_into_research_topic_human_msg_prompt,
    draft_report_generation_prompt,
)
from deep_research.state_scope import (
    AgentState,
    ResearchQuestion,
    AgentInputState,
    DraftReport,
)
from deep_research.usage_tracker import get_tracker
from deep_research.run_logger import get_logger

# ===== UTILITY FUNCTIONS =====


def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%d/%m/%Y, %H:%M:%S")


def _handle_api_error(error: Exception) -> RuntimeError:
    """Handle API errors and raise appropriate RuntimeError."""
    error_msg = str(error)
    if (
        "429" in error_msg
        or "quota" in error_msg.lower()
        or "insufficient_quota" in error_msg.lower()
    ):
        return RuntimeError(
            "OpenAI API Quota Exceeded: Your OpenAI API key has exceeded its quota or billing limit. "
            "Please check your OpenAI account billing and usage at https://platform.openai.com/usage. "
            "You may need to add payment information or upgrade your plan."
        )
    elif "401" in error_msg or (
        "invalid" in error_msg.lower() and "api key" in error_msg.lower()
    ):
        return RuntimeError(
            "OpenAI API Key Error: Your API key is invalid or expired. "
            "Please check your OPENAI_API_KEY in your .env file or environment variables."
        )
    else:
        return RuntimeError(
            f"Error: {error_msg}. Please check your API configuration and try again."
        )


# ===== CONFIGURATION =====

# Initialize model
model = get_model()
creative_model = get_model()

# ===== WORKFLOW NODES =====


def clarify_with_user(
    state: AgentState,
) -> Command[Literal["write_research_brief"]]:
    """
    Determine if the user's request contains sufficient information to proceed with research.

    Note: Initial report handling is done in the full graph (research_agent_full.py),
    not in the scope graph. This function only handles the normal research workflow.
    """
    # Normal flow: proceed to research brief generation
    # Initial report routing to red_team_evaluation is handled in research_agent_full.py
    return Command(goto="write_research_brief")


def write_research_brief(state: AgentState) -> Command[Literal["write_draft_report"]]:
    """Transform the conversation history into a comprehensive research brief."""
    structured_output_model = model.with_structured_output(ResearchQuestion)
    user_request = state.get("messages", [])[-1]

    try:
        response = structured_output_model.invoke(
            [
                HumanMessage(
                    content=transform_messages_into_research_topic_human_msg_prompt.format(
                        messages=get_buffer_string(messages=[user_request]),
                        date=get_today_str(),
                    )
                )
            ]
        )

        tracker = get_tracker()
        tracker.track_openai_response(
            response,
            model_name="writer_model",
            step_name="scope.write_research_brief",
            metadata={
                "brief_length": (
                    len(response.research_brief)
                    if hasattr(response, "research_brief")
                    else 0
                )
            },
        )

        original_user_request = state.get("original_user_request") or user_request

        return Command(
            goto="write_draft_report",
            update={
                "research_brief": response.research_brief,
                "user_request": user_request,
                "original_user_request": original_user_request,
            },
        )
    except Exception as e:
        raise _handle_api_error(e) from e


def write_draft_report(state: AgentState) -> Command[Literal["__end__"]]:
    """Synthesize all research findings into a comprehensive final report."""
    structured_output_model = creative_model.with_structured_output(DraftReport)
    research_brief = state.get("research_brief", "")
    draft_report_prompt = draft_report_generation_prompt.format(
        research_brief=research_brief, date=get_today_str()
    )

    try:
        response = structured_output_model.invoke(
            [HumanMessage(content=draft_report_prompt)]
        )

        tracker = get_tracker()
        tracker.track_openai_response(
            response,
            model_name="writer_model",
            step_name="scope.write_draft_report",
            metadata={"research_brief_length": len(research_brief)},
        )

        return {
            "research_brief": research_brief,
            "draft_report": response.draft_report,
            "supervisor_messages": [
                "Here is the draft report: " + response.draft_report,
                research_brief,
            ],
        }
    except Exception as e:
        raise _handle_api_error(e) from e


# ===== INITIAL REPORT ENRICHMENT NODE (used in full graph) =====


def _extract_gaps_from_feedback(red_team_feedback: dict) -> str:
    """Extract and format gaps from red team feedback."""
    gaps = []
    gaps.extend(red_team_feedback.get("priority_issues", []))
    gaps.extend(red_team_feedback.get("specific_suggestions", []))

    gap_lines = []
    for idx, item in enumerate(gaps[:10], 1):
        if isinstance(item, dict):
            issue = item.get("issue") or item.get("suggestion") or str(item)
            severity = item.get("severity", "")
            gap_lines.append(
                f"{idx}. [{severity.upper()}] {issue}"
                if severity
                else f"{idx}. {issue}"
            )
        else:
            gap_lines.append(f"{idx}. {item}")
    return "\n".join(gap_lines) if gap_lines else "No explicit gaps listed."


# ===== EVIDENCE REFRESH NODE (used in full graph) =====


# ===== GRAPH CONSTRUCTION =====

# Build the scoping workflow
deep_researcher_builder = StateGraph(AgentState, input_schema=AgentInputState)

# Add workflow nodes
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("write_research_brief", write_research_brief)
deep_researcher_builder.add_node("write_draft_report", write_draft_report)

# Add workflow edges
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("write_research_brief", "write_draft_report")
deep_researcher_builder.add_edge("write_draft_report", END)

# Compile the workflow
scope_research = deep_researcher_builder.compile()
