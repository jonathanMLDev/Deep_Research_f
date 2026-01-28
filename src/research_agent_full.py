"""
Full Multi-Agent Research System

This module integrates all components of the research system:
- User clarification and scoping
- Research brief generation
- Multi-agent research coordination
- Final report generation

The system orchestrates the complete research workflow from initial user
input through final report delivery.
"""

from pathlib import Path

from dotenv import load_dotenv

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

from deep_research.utils import get_today_str
from deep_research.prompts import (
    final_report_generation_with_helpfulness_insightfulness_hit_citation_prompt,
    enrich_initial_report_with_findings_prompt,
)
from deep_research.state_scope import AgentState, AgentInputState
from deep_research.research_agent_scope import (
    clarify_with_user,
    write_research_brief,
    write_draft_report,
)
from deep_research.multi_agent_supervisor import supervisor_agent
from deep_research.usage_tracker import get_tracker
from deep_research.red_team_evaluator import RedTeamEvaluator
from deep_research.model_config import get_model
from deep_research.run_logger import get_logger

# ===== Config =====
load_dotenv()

writer_model = get_model(max_tokens=32000)

# ===== HELPER FUNCTIONS =====


def _save_report_snapshot(report_content: str, iteration_idx: int = 0) -> None:
    """Save report snapshot for traceability."""
    try:
        save_dir = Path("reports/iteration_reports")
        save_dir.mkdir(parents=True, exist_ok=True)
        safe_ts = get_today_str().replace(":", "-").replace("/", "-").replace(" ", "_")
        snapshot_path = save_dir / f"final_report_iter_{iteration_idx}_{safe_ts}.md"
        snapshot_path.write_text(report_content, encoding="utf-8")
        try:
            get_logger().log_step(
                "blue_team.final_report_snapshot",
                "Saved iteration report snapshot",
                extra={"iteration": iteration_idx, "path": str(snapshot_path)},
            )
        except Exception:
            pass
    except Exception:
        pass


def _log_step(step_name: str, message: str, **kwargs) -> None:
    """Log a step, ignoring errors."""
    try:
        get_logger().log_step(step_name, message, **kwargs)
    except Exception:
        pass


def _build_main_report_prompt(
    state: AgentState, initial_report: str, findings: str
) -> tuple[str, str]:
    """Build final report prompt and return (prompt, stage_label)."""
    if initial_report and findings:
        print("\n" + "=" * 80)
        print("[BLUE TEAM] Enriching initial report with new research findings...")
        print("=" * 80)
        prompt = enrich_initial_report_with_findings_prompt.format(
            initial_report=initial_report,
            findings=findings,
            research_brief=state.get("research_brief", ""),
            user_request=state.get("user_request", ""),
        )
        return prompt, "enrichment"
    else:
        print("\n" + "=" * 80)
        print("[BLUE TEAM] Generating initial final report...")
        print("=" * 80)
        prompt = final_report_generation_with_helpfulness_insightfulness_hit_citation_prompt.format(
            research_brief=state.get("research_brief", ""),
            findings=findings,
            date=get_today_str(),
            draft_report=state.get("draft_report", ""),
            user_request=state.get("user_request", ""),
        )
        return prompt, "initial_report"


# ===== FINAL REPORT GENERATION =====


async def main_report_generation(state: AgentState):
    """Generate initial final report or enrich initial report with new research findings."""
    initial_report = state.get("initial_report")
    notes = state.get("notes", [])
    findings = "\n".join(notes)

    main_report_prompt, stage_label = _build_main_report_prompt(
        state, initial_report, findings
    )
    main_report = await writer_model.ainvoke([HumanMessage(content=main_report_prompt)])

    tracker = get_tracker()
    token_usage = tracker.track_openai_response(
        main_report,
        model_name="writer_model",
        step_name="main_report_generation",
        metadata={"stage": stage_label, "has_initial_report": bool(initial_report)},
    )
    report_content = main_report.content
    report_length = len(report_content)
    action = "enriched" if (initial_report and notes) else "generated"
    print(f"[BLUE TEAM] ✓ Initial report {action} ({report_length:,} characters)")
    print(f"[BLUE TEAM] → Proceeding to red team evaluation...\n")

    _save_report_snapshot(report_content)

    _log_step(
        "blue_team.final_report_generation",
        "Initial final report generated",
        tokens=token_usage,
        extra={"char_length": report_length},
        model_label="writer_model",
    )

    return {
        "main_report": report_content,
        "messages": ["Initial final report generated"],
    }


# ===== FINALIZATION NODE =====


async def finalize_report(state: AgentState) -> dict:
    """Finalize the report by running red team evaluation."""
    print("\n" + "=" * 80)
    print("[FINALIZATION] Red Team Evaluation")
    print("=" * 80)

    report_to_finalize = state.get("main_report", "")
    if not report_to_finalize:
        print("[FINALIZATION] ⚠️ No main_report found in state, skipping finalization")
        print("=" * 80 + "\n")
        return {}

    try:
        evaluator = RedTeamEvaluator()
        research_query = state.get("research_query", state.get("user_request", ""))
        red_team_evaluation = await evaluator.evaluate_report(
            report_to_finalize, research_query
        )

        print("[FINALIZATION] ✓ Red team evaluation completed")
        print("=" * 80 + "\n")

        return {
            "main_report": report_to_finalize,
            "red_team_evaluation": red_team_evaluation,
            "messages": ["Red team evaluation completed"],
        }
    except Exception as e:
        print(f"[FINALIZATION] ⚠️ Error during evaluation: {e}")
        print("[FINALIZATION] Falling back to main_report without evaluation")
        print("=" * 80 + "\n")
        _log_step(
            "finalize_report.error",
            f"Evaluation failed, using main_report as fallback: {str(e)}",
            extra={"error_type": type(e).__name__},
        )
        # Fallback: return main_report if evaluation fails
        return {
            "main_report": report_to_finalize,
            "messages": ["Report finalized (fallback: evaluation step failed)"],
        }


# ===== GRAPH CONSTRUCTION =====

deep_researcher_builder = StateGraph(AgentState, input_schema=AgentInputState)

deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("write_research_brief", write_research_brief)
deep_researcher_builder.add_node("write_draft_report", write_draft_report)
deep_researcher_builder.add_node("supervisor_subgraph", supervisor_agent)
deep_researcher_builder.add_node("main_report_generation", main_report_generation)
deep_researcher_builder.add_node("finalize_report", finalize_report)

deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("write_research_brief", "write_draft_report")
deep_researcher_builder.add_edge("write_draft_report", "supervisor_subgraph")
deep_researcher_builder.add_edge("supervisor_subgraph", "main_report_generation")
deep_researcher_builder.add_edge("main_report_generation", "finalize_report")
deep_researcher_builder.add_edge("finalize_report", END)

agent = deep_researcher_builder.compile()
