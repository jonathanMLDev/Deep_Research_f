"""
Shared main process for deep research tasks.

This module centralizes the run-and-save workflow used by tasks in the
``tasks`` directory. Tasks only need to construct a query and call
``run_main_process`` with the desired output settings.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Iterable, Optional, Tuple

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from deep_research.research_agent_full import deep_researcher_builder
from deep_research.usage_tracker import get_tracker
from deep_research.pricing_calculator import calculate_total_cost, format_pricing_report
from deep_research.report_productor import (
    create_summary,
    fix_report,
    recreate_report,
    format_evaluation_report,
)
from deep_research.dataclasses import ObjectivityScore
from deep_research.run_logger import RunLogger, set_logger

# Defaults
DEFAULT_RECURSION_LIMIT = 15


# --------------------------------------------------------------------------- #
# Environment helpers
# --------------------------------------------------------------------------- #
def load_env_file() -> bool:
    """Load environment variables from .env in project root or cwd."""
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        return True
    fallback = Path(".env")
    if fallback.exists():
        load_dotenv(fallback)
        return True
    return False


def check_api_keys(
    required: Iterable[str] = ("OPENAI_API_KEY", "TAVILY_API_KEY")
) -> bool:
    """Ensure required API keys are present."""
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        print(f"[ERROR] Missing API keys: {', '.join(missing)}")
        return False
    return True


# --------------------------------------------------------------------------- #
# Core runner
# --------------------------------------------------------------------------- #
def _write_report_header(
    f, report_title: str, preface_lines: Optional[Iterable[str]]
) -> None:
    """Write report header and preface."""
    f.write(f"# {report_title}\n\n")
    f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
    f.write("---\n\n")
    if preface_lines:
        for line in preface_lines:
            f.write(f"{line}\n")
        f.write("\n---\n\n")


def _write_usage_stats(f, usage_stats: dict) -> None:
    """Write usage statistics section."""
    openai_stats = usage_stats.get("openai", {})
    tavily_stats = usage_stats.get("tavily", {})
    f.write("## Usage Statistics\n\n")
    f.write(f"- **Input tokens:** {openai_stats.get('prompt_tokens', 0):,}\n")
    f.write(f"- **Output tokens:** {openai_stats.get('completion_tokens', 0):,}\n")
    f.write(f"- **Total tokens:** {openai_stats.get('total_tokens', 0):,}\n")
    f.write(f"- **Tavily calls:** {tavily_stats.get('api_calls', 0):,}\n\n")
    f.write("---\n\n")


def _write_bias_metrics(
    f, bias_metrics: dict, issues: dict, source_quality: dict
) -> None:
    """Write bias metrics, issues, and source quality to file."""
    f.write(
        f"- **Bias Issues:** {bias_metrics.get('missing_counter_evidence_count', 0) + bias_metrics.get('confirmation_bias_indicators_count', 0)}\n"
    )
    f.write(f"- **Unsupported Claims:** {issues.get('unsupported_claims_count', 0)}\n")
    f.write(
        f"- **Source Credibility:** {source_quality.get('credibility_score', 0):.1%}\n\n"
    )


def _setup_environment() -> None:
    """Load environment variables and check API keys."""
    load_env_file()
    if not check_api_keys():
        sys.exit(1)


def _setup_logging_and_tracking(task_name: str, output_path: str) -> RunLogger:
    """Initialize logger and reset tracker."""
    logger = RunLogger(task_name=task_name, log_dir=output_path)
    set_logger(logger)
    tracker = get_tracker()
    tracker.reset()
    return logger


def _prepare_agent_and_config(thread_id: str, recursion_limit: int) -> Tuple[Any, dict]:
    """Prepare agent and thread configuration."""
    memory = InMemorySaver()
    thread_config = {
        "configurable": {"thread_id": thread_id, "recursion_limit": recursion_limit}
    }
    agent = deep_researcher_builder.compile(checkpointer=memory)
    return agent, thread_config


def _log_task_start(
    logger: RunLogger, thread_id: str, query: str, initial_report: Optional[str]
) -> None:
    """Log task start, query, and initial report if present."""
    try:
        logger.log_step(
            "task.start", "Research started", extra={"thread_id": thread_id}
        )
        logger.log_step(
            "task.query",
            "Research query prepared",
            extra={"query_preview": query[:500]},
        )
        if initial_report:
            logger.log_step(
                "task.initial_report",
                "Initial report provided - will be enriched based on red team feedback",
                extra={"initial_report_length": len(initial_report)},
            )
    except Exception:
        pass


def _prepare_input_state(query: str, initial_report: Optional[str]) -> dict:
    """Prepare input state for agent invocation."""
    input_state = {"messages": [HumanMessage(content=query)]}
    if initial_report:
        input_state["initial_report"] = initial_report
    return input_state


def _collect_usage_stats(tracker: Any, result: dict) -> Tuple[dict, dict]:
    """Finalize tracker and collect usage statistics."""
    tracker.finalize()
    usage_stats = tracker.get_stats().to_dict()
    result["usage_stats"] = usage_stats
    cost_breakdown = calculate_total_cost(usage_stats)
    return usage_stats, cost_breakdown


def _prepare_output_paths(output_path: str, report_prefix: str) -> Tuple[Path, Path]:
    """Create output directory and generate report path."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"{report_prefix}_{timestamp}.md"
    return output_dir, report_path


def _setup_logger_file(logger: RunLogger, report_path: Path) -> None:
    """Set logger file path, ignoring errors."""
    try:
        logger.set_log_file(report_path)
    except Exception:
        pass


async def _produce_reports(
    main_report: str,
    red_team_evaluation: ObjectivityScore,
    research_query: str,
    output_dir: Path,
    report_path: Path,
) -> Tuple[Path, Path, Path]:
    """
    Produce cleaned_report, fixed_report, and summary_report.

    Returns:
        Tuple of (cleaned_report_path, fixed_report_path, summary_report_path)
    """
    red_team_report = format_evaluation_report(red_team_evaluation)

    # Produce cleaned report (remove invalid URLs and fix inconsistent values/claims)
    cleaned_report = await fix_report(main_report, red_team_evaluation)

    # Produce fixed report (recreate with recommendations)
    fixed_report = await recreate_report(
        cleaned_report,
        research_query,
        red_team_evaluation.recommendations,
    )

    # Produce summary report
    summary_report = await create_summary(
        main_report, red_team_report, user_query=research_query
    )

    # Write reports to files
    cleaned_path = output_dir / f"{report_path.stem}_cleaned.md"
    fixed_path = output_dir / f"{report_path.stem}_fixed.md"
    summary_path = output_dir / f"{report_path.stem}_summary.md"

    cleaned_path.write_text(cleaned_report, encoding="utf-8")
    fixed_path.write_text(fixed_report, encoding="utf-8")
    summary_path.write_text(summary_report, encoding="utf-8")

    return cleaned_path, fixed_path, summary_path


def _write_main_report(
    report_path: Path,
    report_title: str,
    preface_lines: Optional[Iterable[str]],
    usage_stats: dict,
    cost_breakdown: dict,
    main_report: str,
    red_team_evaluation: Optional[ObjectivityScore],
) -> None:
    """Write main report content to file."""
    with report_path.open("w", encoding="utf-8") as f:
        _write_report_header(f, report_title, preface_lines)
        _write_usage_stats(f, usage_stats)
        f.write("## Pricing Information\n\n")
        f.write(format_pricing_report(cost_breakdown))
        f.write("---\n\n")
        if red_team_evaluation:
            _write_red_team_evaluation_summary(f, red_team_evaluation)
        f.write("## Research Report\n\n")
        f.write(main_report)


def _write_red_team_evaluation_summary(
    f, red_team_evaluation: ObjectivityScore
) -> None:
    """Write full red team evaluation report."""
    f.write("## Red Team Evaluation\n\n")
    red_team_report = format_evaluation_report(red_team_evaluation)
    f.write(red_team_report)
    f.write("\n---\n\n")


def _finalize_logging(
    logger: RunLogger,
    report_path: Path,
    cleaned_path: Path,
    fixed_path: Path,
    summary_path: Path,
    usage_stats: dict,
    cost_breakdown: dict,
) -> None:
    """Finalize logging with report paths and statistics."""
    try:
        logger.log_step(
            "report.saved",
            "All reports saved",
            extra={
                "main_report_path": str(report_path),
                "cleaned_report_path": str(cleaned_path),
                "fixed_report_path": str(fixed_path),
                "summary_report_path": str(summary_path),
            },
        )
        logger.finalize(
            usage_stats=usage_stats,
            cost_breakdown=cost_breakdown,
            log_path=report_path.with_suffix(".log"),
        )
    except Exception:
        pass


async def run_main_process(
    query: str,
    *,
    output_path: str,
    report_prefix: str,
    task_name: str,
    report_title: str = "Research Report",
    preface_lines: Optional[Iterable[str]] = None,
    thread_id: str = "default",
    recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    initial_report: Optional[str] = None,
) -> Tuple[Path, Optional[Path]]:
    """Run deep research for a query and save report + summary."""
    _setup_environment()
    logger = _setup_logging_and_tracking(task_name, output_path)
    agent, thread_config = _prepare_agent_and_config(thread_id, recursion_limit)
    _log_task_start(logger, thread_id, query, initial_report)

    input_state = _prepare_input_state(query, initial_report)
    result = await agent.ainvoke(input_state, config=thread_config)

    tracker = get_tracker()
    usage_stats, cost_breakdown = _collect_usage_stats(tracker, result)
    output_dir, report_path = _prepare_output_paths(output_path, report_prefix)
    _setup_logger_file(logger, report_path)

    # Extract main_report and red_team_evaluation from result
    main_report = result.get("main_report", "")
    red_team_evaluation = result.get("red_team_evaluation")

    if not main_report:
        raise ValueError("No main_report found in result")

    # Write main report
    _write_main_report(
        report_path,
        report_title,
        preface_lines,
        usage_stats,
        cost_breakdown,
        main_report,
        red_team_evaluation,
    )

    # Produce cleaned, fixed, summary, and red team evaluation reports
    if red_team_evaluation:
        cleaned_path, fixed_path, summary_path = await _produce_reports(
            main_report, red_team_evaluation, query, output_dir, report_path
        )
    else:
        # If no red team evaluation, create minimal reports
        cleaned_path = output_dir / f"{report_path.stem}_cleaned.md"
        fixed_path = output_dir / f"{report_path.stem}_fixed.md"
        summary_path = output_dir / f"{report_path.stem}_summary.md"
        cleaned_path.write_text(main_report, encoding="utf-8")
        fixed_path.write_text(main_report, encoding="utf-8")
        summary_content = await create_summary(main_report, "", user_query=query)
        summary_path.write_text(summary_content, encoding="utf-8")

    _finalize_logging(
        logger,
        report_path,
        cleaned_path,
        fixed_path,
        summary_path,
        usage_stats,
        cost_breakdown,
    )

    return report_path, summary_path


def execute_main_process(
    query: str,
    *,
    output_path: str,
    report_prefix: str,
    task_name: str,
    report_title: str = "Research Report",
    preface_lines: Optional[Iterable[str]] = None,
    thread_id: str = "default",
    recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    initial_report: Optional[str] = None,
) -> Tuple[Path, Optional[Path]]:
    """
    Synchronous helper wrapping run_main_process for task files.
    """
    import asyncio

    return asyncio.run(
        run_main_process(
            query,
            output_path=output_path,
            report_prefix=report_prefix,
            task_name=task_name,
            report_title=report_title,
            preface_lines=preface_lines,
            thread_id=thread_id,
            recursion_limit=recursion_limit,
            initial_report=initial_report,
        )
    )
