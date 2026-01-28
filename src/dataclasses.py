"""
Data classes for the deep research system.

This module contains all dataclasses used across the project for better
organization and to avoid circular imports.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


# ===== Red Team Evaluation Dataclasses =====


@dataclass
class BiasMetrics:
    """Metrics for detecting bias in research reports."""

    one_sided_score: float = 0.0  # 0-1, higher = more one-sided
    missing_counter_evidence: List[str] = field(default_factory=list)
    confirmation_bias_indicators: List[str] = field(default_factory=list)
    source_diversity_score: float = 0.0  # 0-1, higher = more diverse sources
    quantitative_ratio: float = 0.0  # Ratio of quantitative to qualitative claims


@dataclass
class SourceQualityMetrics:
    """Metrics for assessing source quality."""

    total_sources: int = 0
    valid_sources: int = 0
    primary_sources: int = 0  # Official, authoritative sources
    secondary_sources: int = 0  # News, blogs, aggregators
    academic_sources: int = 0
    source_credibility_score: float = 0.0  # 0-1, higher = more credible
    missing_citations: List[str] = field(default_factory=list)
    invalid_sources: List[str] = field(default_factory=list)


@dataclass
class ClaimSourceConsistency:
    """Metrics for claim-source consistency verification."""

    numerical_inconsistencies: List[Dict[str, Any]] = field(default_factory=list)
    contextual_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    unverifiable_claims: List[Dict[str, Any]] = field(default_factory=list)
    verified_claims_count: int = 0
    consistency_score: float = 0.0  # 0-1, higher = more consistent


@dataclass
class ObjectivityScore:
    """Overall objectivity assessment."""

    overall_score: float = 0.0  # 0-1, higher = more objective
    bias_metrics: BiasMetrics = field(default_factory=BiasMetrics)
    source_quality: SourceQualityMetrics = field(default_factory=SourceQualityMetrics)
    unsupported_claims: List[str] = field(default_factory=list)
    counter_evidence_gaps: List[str] = field(default_factory=list)
    claim_source_consistency: ClaimSourceConsistency = field(
        default_factory=ClaimSourceConsistency
    )
    recommendations: List[str] = field(default_factory=list)


# ===== Usage Tracking Dataclasses =====


@dataclass
class UsageStats:
    """Container for usage statistics."""

    # OpenAI/OpenRouter token usage (aggregated)
    openai_prompt_tokens: int = 0
    openai_completion_tokens: int = 0
    openai_total_tokens: int = 0

    # Token usage by model (for separate tracking)
    model_usage: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "summarization_model": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "writer_model": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "evaluator_model": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
    )

    # Tavily API usage
    tavily_api_calls: int = 0

    # Timestamps
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_openai_usage(
        self, prompt_tokens: int, completion_tokens: int, model_name: str = None
    ):
        """Add OpenAI token usage."""
        self.openai_prompt_tokens += prompt_tokens
        self.openai_completion_tokens += completion_tokens
        self.openai_total_tokens += prompt_tokens + completion_tokens

        if model_name:
            if model_name not in self.model_usage:
                self.model_usage[model_name] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            self.model_usage[model_name]["prompt_tokens"] += prompt_tokens
            self.model_usage[model_name]["completion_tokens"] += completion_tokens
            self.model_usage[model_name]["total_tokens"] += (
                prompt_tokens + completion_tokens
            )

    def add_tavily_call(self):
        """Increment Tavily API call count."""
        self.tavily_api_calls += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "openai": {
                "prompt_tokens": self.openai_prompt_tokens,
                "completion_tokens": self.openai_completion_tokens,
                "total_tokens": self.openai_total_tokens,
            },
            "models": {
                model: {
                    "prompt_tokens": stats["prompt_tokens"],
                    "completion_tokens": stats["completion_tokens"],
                    "total_tokens": stats["total_tokens"],
                }
                for model, stats in self.model_usage.items()
            },
            "tavily": {"api_calls": self.tavily_api_calls},
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    def get_summary(self) -> str:
        """Get a formatted summary string."""
        lines = [
            "=" * 60,
            "API Usage Summary",
            "=" * 60,
            "",
            "OpenAI/OpenRouter:",
            f"  Input tokens:  {self.openai_prompt_tokens:,}",
            f"  Output tokens: {self.openai_completion_tokens:,}",
            f"  Total tokens:  {self.openai_total_tokens:,}",
            "",
            "Tavily:",
            f"  API calls:     {self.tavily_api_calls:,}",
            "",
        ]

        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            lines.append(f"Duration: {duration}")
            lines.append("")

        return "\n".join(lines)


# ===== Logging Dataclasses =====


@dataclass
class LogEntry:
    """Single log entry for a step in the workflow."""

    timestamp: datetime
    step: str
    content: str
    tokens: Optional[Dict[str, int]] = None
    cost: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None
    model_label: Optional[str] = None
