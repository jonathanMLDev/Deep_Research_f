"""
Pricing Calculator Module

Calculates costs based on token usage and API calls for different LLM providers.
"""

import os
from typing import Dict, Any, Optional


# Pricing per 1K tokens (as of 2024-2025)
# OpenAI pricing
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-5": {"input": 2.50, "output": 10.00},  # Assuming similar to gpt-4o
    "gpt-5-nano": {"input": 0.10, "output": 0.40},  # Estimated for nano model
}

# OpenRouter pricing (approximate, varies by model)
# These are estimates - actual pricing may vary
OPENROUTER_PRICING = {
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "openai/gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "openai/gpt-5": {"input": 2.50, "output": 10.00},
    "openai/gpt-5-nano": {"input": 0.10, "output": 0.40},
    "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
}

# Tavily API pricing (as of 2024)
TAVILY_PRICING = {
    "api_call": 0.008,  # $0.10 per API call (approximate, may vary by plan)
}


def get_model_name() -> str:
    """Get the current model name from environment variables."""
    use_openrouter = os.getenv("USE_OPENROUTER", "false").lower() == "true"

    if use_openrouter:
        return os.getenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o")
    else:
        return os.getenv("OPENAI_MODEL", "gpt-5")


def resolve_model_identifier(model_label: str) -> str:
    """
    Map an internal model label to the concrete model identifier from environment variables.

    Args:
        model_label: One of "summarization_model", "writer_model", "evaluator_model", or a
            direct model identifier. If the label is not recognized, the input is returned.

    Returns:
        Concrete model identifier string.
    """
    use_openrouter = os.getenv("USE_OPENROUTER", "false").lower() == "true"

    if model_label == "summarization_model":
        if use_openrouter:
            return os.getenv("OPENROUTER_LIGHT_MODEL", "openai/gpt-5-nano")
        return os.getenv("OPENAI_MODEL", "gpt-5-nano")

    if model_label == "writer_model":
        if use_openrouter:
            return os.getenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o")
        return os.getenv("OPENAI_MODEL", "gpt-5")

    if model_label == "evaluator_model":
        return os.getenv("EVALUATOR_MODEL", "google/gemini-2.5-flash")

    return model_label


def get_pricing_for_model(model_name: str) -> Dict[str, float]:
    """
    Get pricing for a specific model.

    Args:
        model_name: Model identifier

    Returns:
        Dictionary with 'input' and 'output' prices per 1K tokens
    """
    use_openrouter = os.getenv("USE_OPENROUTER", "false").lower() == "true"

    if use_openrouter:
        pricing = OPENROUTER_PRICING.get(model_name)
        if pricing:
            return pricing
        # Fallback: try to find similar model
        if "gpt-4o" in model_name.lower():
            return OPENROUTER_PRICING.get("openai/gpt-4o", {"input": 2.50, "output": 10.00})
        elif "gpt-4-turbo" in model_name.lower():
            return OPENROUTER_PRICING.get("openai/gpt-4-turbo", {"input": 10.00, "output": 30.00})
        elif "gpt-3.5" in model_name.lower():
            return OPENROUTER_PRICING.get("openai/gpt-3.5-turbo", {"input": 0.50, "output": 1.50})
        elif "nano" in model_name.lower():
            return OPENROUTER_PRICING.get("openai/gpt-5-nano", {"input": 0.10, "output": 0.40})
        else:
            # Default to gpt-4o pricing
            return {"input": 2.50, "output": 10.00}
    else:
        # OpenAI pricing
        pricing = OPENAI_PRICING.get(model_name)
        if pricing:
            return pricing
        # Fallback: try to find similar model
        if "gpt-4o" in model_name.lower() or "gpt-5" in model_name.lower():
            return OPENAI_PRICING.get("gpt-4o", {"input": 2.50, "output": 10.00})
        elif "gpt-4-turbo" in model_name.lower():
            return OPENAI_PRICING.get("gpt-4-turbo", {"input": 10.00, "output": 30.00})
        elif "gpt-3.5" in model_name.lower():
            return OPENAI_PRICING.get("gpt-3.5-turbo", {"input": 0.50, "output": 1.50})
        elif "nano" in model_name.lower():
            return OPENAI_PRICING.get("gpt-5-nano", {"input": 0.10, "output": 0.40})
        else:
            # Default to gpt-4o pricing
            return {"input": 2.50, "output": 10.00}


def calculate_llm_cost(
    input_tokens: int,
    output_tokens: int,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate LLM cost based on token usage.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model_name: Optional model name. If not provided, uses current model from env.

    Returns:
        Dictionary with cost breakdown
    """
    if model_name is None:
        model_name = get_model_name()

    pricing = get_pricing_for_model(model_name)

    # Convert tokens to thousands
    input_k_tokens = input_tokens / 1000000.0
    output_k_tokens = output_tokens / 1000000.0

    # Calculate costs
    input_cost = input_k_tokens * pricing["input"]
    output_cost = output_k_tokens * pricing["output"]
    total_cost = input_cost + output_cost

    return {
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "pricing_per_1k": pricing
    }


def calculate_tavily_cost(api_calls: int) -> Dict[str, Any]:
    """
    Calculate Tavily API cost.

    Args:
        api_calls: Number of Tavily API calls

    Returns:
        Dictionary with cost breakdown
    """
    cost_per_call = TAVILY_PRICING["api_call"]
    total_cost = api_calls * cost_per_call

    return {
        "api_calls": api_calls,
        "cost_per_call": cost_per_call,
        "total_cost": total_cost
    }


def calculate_total_cost(
    usage_stats: Dict[str, Any],
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate total cost from usage statistics, with separate tracking for each model.

    Args:
        usage_stats: Usage statistics dictionary (from UsageTracker)
        model_name: Optional model name (for backward compatibility)

    Returns:
        Dictionary with complete cost breakdown by model
    """
    openai_stats = usage_stats.get("openai", {})
    models_stats = usage_stats.get("models", {})
    tavily_stats = usage_stats.get("tavily", {})

    tavily_calls = tavily_stats.get("api_calls", 0)
    tavily_cost = calculate_tavily_cost(tavily_calls)

    # Calculate costs for each model separately
    model_costs = {}
    total_llm_cost = 0.0

    summarization_model_name = resolve_model_identifier("summarization_model")
    writer_model_name = resolve_model_identifier("writer_model")
    evaluator_model_name = resolve_model_identifier("evaluator_model")

    # Calculate cost for summarization_model
    if "summarization_model" in models_stats:
        summarization_stats = models_stats["summarization_model"]
        input_tokens = summarization_stats.get("prompt_tokens", 0)
        output_tokens = summarization_stats.get("completion_tokens", 0)
        if input_tokens > 0 or output_tokens > 0:
            cost = calculate_llm_cost(input_tokens, output_tokens, summarization_model_name)
            model_costs["summarization_model"] = cost
            total_llm_cost += cost["total_cost"]

    # Calculate cost for writer_model
    if "writer_model" in models_stats:
        writer_stats = models_stats["writer_model"]
        input_tokens = writer_stats.get("prompt_tokens", 0)
        output_tokens = writer_stats.get("completion_tokens", 0)
        if input_tokens > 0 or output_tokens > 0:
            cost = calculate_llm_cost(input_tokens, output_tokens, writer_model_name)
            model_costs["writer_model"] = cost
            total_llm_cost += cost["total_cost"]

    # Calculate cost for evaluator_model (red team)
    if "evaluator_model" in models_stats:
        evaluator_stats = models_stats["evaluator_model"]
        input_tokens = evaluator_stats.get("prompt_tokens", 0)
        output_tokens = evaluator_stats.get("completion_tokens", 0)
        if input_tokens > 0 or output_tokens > 0:
            cost = calculate_llm_cost(input_tokens, output_tokens, evaluator_model_name)
            model_costs["evaluator_model"] = cost
            total_llm_cost += cost["total_cost"]

    # For backward compatibility: if no model-specific stats, use aggregate
    if not model_costs:
        input_tokens = openai_stats.get("prompt_tokens", 0)
        output_tokens = openai_stats.get("completion_tokens", 0)
        if input_tokens > 0 or output_tokens > 0:
            llm_cost = calculate_llm_cost(input_tokens, output_tokens, model_name or writer_model_name)
            model_costs["aggregate"] = llm_cost
            total_llm_cost = llm_cost["total_cost"]

    total_cost = total_llm_cost + tavily_cost["total_cost"]

    return {
        "models": model_costs,
        "tavily": tavily_cost,
        "total_llm_cost": total_llm_cost,
        "total_cost": total_cost,
        "breakdown": {
            "summarization_model": model_costs.get("summarization_model", {}).get("total_cost", 0.0),
            "writer_model": model_costs.get("writer_model", {}).get("total_cost", 0.0),
            "evaluator_model": model_costs.get("evaluator_model", {}).get("total_cost", 0.0),
            "tavily": tavily_cost["total_cost"]
        }
    }


def format_pricing_report(cost_breakdown: Dict[str, Any]) -> str:
    """
    Format pricing information as markdown with separate costs for each model.

    Args:
        cost_breakdown: Cost breakdown dictionary from calculate_total_cost

    Returns:
        Formatted markdown string
    """
    models = cost_breakdown.get("models", {})
    tavily = cost_breakdown.get("tavily", {})

    lines = [
        "## Pricing Information",
        "",
    ]

    # Format costs for each model separately
    if "summarization_model" in models:
        summarization = models["summarization_model"]
        lines.extend([
            "### Summarization Model Costs",
            "",
            f"**Model:** {summarization['model']}",
            f"- **Input tokens:** {summarization['input_tokens']:,}",
            f"- **Output tokens:** {summarization['output_tokens']:,}",
            f"- **Input cost:** ${summarization['input_cost']:.2f} (${summarization['pricing_per_1k']['input']:.2f} per 1K tokens)",
            f"- **Output cost:** ${summarization['output_cost']:.2f} (${summarization['pricing_per_1k']['output']:.2f} per 1K tokens)",
            f"- **Summarization model total:** ${summarization['total_cost']:.2f}",
            "",
        ])

    if "writer_model" in models:
        writer = models["writer_model"]
        lines.extend([
            "### Writer Model Costs",
            "",
            f"**Model:** {writer['model']}",
            f"- **Input tokens:** {writer['input_tokens']:,}",
            f"- **Output tokens:** {writer['output_tokens']:,}",
            f"- **Input cost:** ${writer['input_cost']:.2f} (${writer['pricing_per_1k']['input']:.2f} per 1K tokens)",
            f"- **Output cost:** ${writer['output_cost']:.2f} (${writer['pricing_per_1k']['output']:.2f} per 1K tokens)",
            f"- **Writer model total:** ${writer['total_cost']:.2f}",
            "",
        ])

    if "evaluator_model" in models:
        evaluator = models["evaluator_model"]
        lines.extend([
            "### Evaluator Model Costs (Red Team)",
            "",
            f"**Model:** {evaluator['model']}",
            f"- **Input tokens:** {evaluator['input_tokens']:,}",
            f"- **Output tokens:** {evaluator['output_tokens']:,}",
            f"- **Input cost:** ${evaluator['input_cost']:.2f} (${evaluator['pricing_per_1k']['input']:.2f} per 1K tokens)",
            f"- **Output cost:** ${evaluator['output_cost']:.2f} (${evaluator['pricing_per_1k']['output']:.2f} per 1K tokens)",
            f"- **Evaluator model total:** ${evaluator['total_cost']:.2f}",
            "",
        ])

    # Fallback for aggregate (backward compatibility)
    if "aggregate" in models:
        aggregate = models["aggregate"]
        lines.extend([
            "### LLM Costs (Aggregate)",
            "",
            f"**Model:** {aggregate['model']}",
            f"- **Input tokens:** {aggregate['input_tokens']:,}",
            f"- **Output tokens:** {aggregate['output_tokens']:,}",
            f"- **Input cost:** ${aggregate['input_cost']:.2f} (${aggregate['pricing_per_1k']['input']:.2f} per 1K tokens)",
            f"- **Output cost:** ${aggregate['output_cost']:.2f} (${aggregate['pricing_per_1k']['output']:.2f} per 1K tokens)",
            f"- **LLM total:** ${aggregate['total_cost']:.2f}",
            "",
        ])

    lines.extend([
        "### Tavily API Costs",
        "",
        f"- **API calls:** {tavily.get('api_calls', 0):,}",
        f"- **Cost per call:** ${tavily.get('cost_per_call', 0.008):.3f}",
        f"- **Tavily total:** ${tavily.get('total_cost', 0.0):.2f}",
        "",
        "### Total Cost",
        "",
        f"**Total LLM cost:** ${cost_breakdown.get('total_llm_cost', 0.0):.2f}",
        f"**Estimated total cost:** ${cost_breakdown.get('total_cost', 0.0):.2f}",
        "",
        "---",
        ""
    ])

    return "\n".join(lines)

