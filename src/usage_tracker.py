"""
Token and API Usage Tracking Module

Tracks token usage for OpenAI/OpenRouter and API calls for Tavily separately.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from deep_research.dataclasses import UsageStats


class UsageTracker:
    """Global usage tracker instance."""

    def __init__(self):
        self.stats = UsageStats()
        self.stats.start_time = datetime.now()

    def _extract_tokens_from_response_metadata(
        self, response: Any, model_name: str
    ) -> Optional[Dict[str, int]]:
        """Extract tokens from response_metadata attribute."""
        if not hasattr(response, "response_metadata"):
            return None

        metadata = response.response_metadata
        if not metadata:
            return None

        usage = metadata.get("token_usage", {})
        if not usage:
            return None

        prompt_tokens = usage.get("prompt_tokens", 0) or usage.get("prompt", 0)
        completion_tokens = usage.get("completion_tokens", 0) or usage.get(
            "completion", 0
        )

        if prompt_tokens or completion_tokens:
            self.stats.add_openai_usage(prompt_tokens, completion_tokens, model_name)
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        return None

    def _extract_tokens_from_usage_attr(
        self, response: Any, model_name: str
    ) -> Optional[Dict[str, int]]:
        """Extract tokens from usage attribute."""
        if not hasattr(response, "usage"):
            return None

        usage = response.usage
        if not usage:
            return None

        prompt_tokens = getattr(usage, "prompt_tokens", 0) or getattr(
            usage, "prompt", 0
        )
        completion_tokens = getattr(usage, "completion_tokens", 0) or getattr(
            usage, "completion", 0
        )

        if prompt_tokens or completion_tokens:
            self.stats.add_openai_usage(prompt_tokens, completion_tokens, model_name)
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        return None

    def _extract_tokens_from_dict(
        self, response: dict, model_name: str
    ) -> Optional[Dict[str, int]]:
        """Extract tokens from dict response."""
        metadata = response.get("response_metadata", {})
        usage = metadata.get("token_usage", {})
        if not usage:
            return None

        prompt_tokens = usage.get("prompt_tokens", 0) or usage.get("prompt", 0)
        completion_tokens = usage.get("completion_tokens", 0) or usage.get(
            "completion", 0
        )

        if prompt_tokens or completion_tokens:
            self.stats.add_openai_usage(prompt_tokens, completion_tokens, model_name)
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        return None

    def _log_token_usage(
        self,
        token_dict: Dict[str, int],
        step_name: str,
        model_name: str,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Log token usage if available."""
        if not token_dict:
            return

        try:
            from deep_research.run_logger import get_logger

            logger = get_logger()
            logger.log_step(
                step_name or "llm_call",
                f"LLM response captured (model={model_name or 'unknown'})",
                tokens=token_dict,
                extra=metadata,
                model_label=model_name,
            )
        except Exception:
            pass

    def track_openai_response(
        self,
        response: Any,
        model_name: str = None,
        step_name: str | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Extract and track token usage from OpenAI/LangChain response."""
        token_dict: Optional[Dict[str, int]] = None

        try:
            token_dict = (
                self._extract_tokens_from_response_metadata(response, model_name)
                or self._extract_tokens_from_usage_attr(response, model_name)
                or (
                    self._extract_tokens_from_dict(response, model_name)
                    if isinstance(response, dict)
                    else None
                )
            )

            if not token_dict:
                from langchain_core.messages import AIMessage

                if isinstance(response, AIMessage):
                    token_dict = self._extract_tokens_from_response_metadata(
                        response, model_name
                    )

        except Exception:
            pass
        finally:
            self._log_token_usage(token_dict, step_name, model_name, metadata)

        return token_dict

    def track_tavily_call(self):
        """Track a Tavily API call."""
        self.stats.add_tavily_call()
        try:
            from deep_research.run_logger import get_logger

            logger = get_logger()
            logger.log_step("tavily_call", "Tavily API call recorded")
        except Exception:
            pass

    def finalize(self):
        """Mark tracking as complete."""
        self.stats.end_time = datetime.now()

    def get_stats(self) -> UsageStats:
        """Get current usage statistics."""
        return self.stats

    def reset(self):
        """Reset all statistics."""
        self.stats = UsageStats()
        self.stats.start_time = datetime.now()


# Global tracker instance
_global_tracker = UsageTracker()


def get_tracker() -> UsageTracker:
    """Get the global usage tracker instance."""
    return _global_tracker


def reset_tracker():
    """Reset the global usage tracker."""
    _global_tracker.reset()
