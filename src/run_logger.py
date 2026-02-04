"""
Run Logger Module

Provides a lightweight logging helper that records step-level events with
timestamps, content, token counts, and per-step cost estimates. The logger is
created by the task entrypoint, registered globally, and referenced by modules
in ``src`` via ``get_logger``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from deep_research.dataclasses import LogEntry


class RunLogger:
    """Task-scoped logger that writes a .log file when finalized."""

    def __init__(self, task_name: str, log_dir: Optional[str | Path] = None):
        self.task_name = task_name
        self.log_dir = Path(log_dir or "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.entries: List[LogEntry] = []
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self.log_path: Optional[Path] = None
        self.usage_stats: Optional[Dict[str, Any]] = None
        self.cost_breakdown: Optional[Dict[str, Any]] = None

    def set_log_file(self, base_path: str | Path):
        """Set the output log file path (converted to .log extension)."""
        path = Path(base_path)
        if path.suffix.lower() != ".log":
            path = path.with_suffix(".log")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path = path

    def log_step(
        self,
        step: str,
        content: str,
        *,
        tokens: Optional[Dict[str, int]] = None,
        cost: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
        model_label: Optional[str] = None,
    ):
        """Record a step with optional token/cost metadata."""
        resolved_cost = cost
        resolved_extra = dict(extra or {})

        # Estimate per-step cost when token counts and model label are provided.
        if resolved_cost is None and tokens and model_label:
            try:
                from deep_research.pricing_calculator import (
                    calculate_llm_cost,
                    resolve_model_identifier,
                )

                prompt_tokens = tokens.get("prompt_tokens", 0)
                completion_tokens = tokens.get("completion_tokens", 0)
                model_name = resolve_model_identifier(model_label)
                cost_info = calculate_llm_cost(
                    prompt_tokens, completion_tokens, model_name
                )
                resolved_cost = cost_info.get("total_cost")
                resolved_extra["cost_breakdown"] = cost_info
            except Exception:
                # Cost estimation is best-effort; never block logging.
                pass

        entry = LogEntry(
            timestamp=datetime.now(),
            step=step,
            content=content,
            tokens=tokens,
            cost=resolved_cost,
            extra=resolved_extra if resolved_extra else None,
            model_label=model_label,
        )
        self.entries.append(entry)

    def finalize(
        self,
        *,
        usage_stats: Optional[Dict[str, Any]] = None,
        cost_breakdown: Optional[Dict[str, Any]] = None,
        log_path: Optional[str | Path] = None,
    ):
        """Finalize and write the log file."""
        if log_path:
            self.set_log_file(log_path)
        if not self.log_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_path = self.log_dir / f"{self.task_name}_{timestamp}.log"

        self.end_time = datetime.now()
        self.usage_stats = usage_stats
        self.cost_breakdown = cost_breakdown
        self._write_log_file()

    def _write_log_file(self):
        """Write collected entries to disk."""
        if not self.log_path:
            return

        lines: List[str] = []
        lines.append(f"Task: {self.task_name}")
        lines.append(f"Start: {self.start_time.isoformat()}")
        if self.end_time:
            lines.append(f"End:   {self.end_time.isoformat()}")
            lines.append(f"Duration: {self.end_time - self.start_time}")
        lines.append("-" * 80)
        lines.append("Step Logs")
        lines.append("-" * 80)

        for entry in self.entries:
            lines.append(
                f"[{entry.timestamp.isoformat()}] {entry.step}: {entry.content}"
            )
            if entry.tokens:
                pt = entry.tokens.get("prompt_tokens", 0)
                ct = entry.tokens.get("completion_tokens", 0)
                tt = entry.tokens.get("total_tokens", pt + ct)
                lines.append(f"  tokens -> prompt: {pt}, completion: {ct}, total: {tt}")
            if entry.model_label:
                lines.append(f"  model_label -> {entry.model_label}")
            if entry.cost is not None:
                lines.append(f"  cost -> ${entry.cost:.4f}")
            if entry.extra:
                lines.append(f"  extra -> {entry.extra}")
            lines.append("")  # Blank line between entries

        if self.usage_stats:
            lines.append("-" * 80)
            lines.append("Usage Stats")
            lines.append("-" * 80)
            lines.append(str(self.usage_stats))

        if self.cost_breakdown:
            lines.append("-" * 80)
            lines.append("Cost Breakdown")
            lines.append("-" * 80)
            lines.append(str(self.cost_breakdown))

        self.log_path.write_text("\n".join(lines), encoding="utf-8")


class _NoOpLogger:
    """Fallback logger when no task logger is registered."""

    def set_log_file(self, base_path: str | Path):
        return None

    def log_step(self, *args, **kwargs):
        return None

    def finalize(self, *args, **kwargs):
        return None


_global_logger: Optional[RunLogger] = None
_noop_logger = _NoOpLogger()


def set_logger(logger: RunLogger):
    """Register the task-scoped logger as global."""
    global _global_logger
    _global_logger = logger


def get_logger() -> RunLogger | _NoOpLogger:
    """Retrieve the registered logger (or a no-op logger if absent)."""
    return _global_logger if _global_logger is not None else _noop_logger
