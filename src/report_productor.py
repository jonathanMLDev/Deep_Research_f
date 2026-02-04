"""
Report Production Module

Handles report cleaning, fixing, recreation, summarization, and evaluation formatting.
"""

import re
from typing import Any, Dict, List
from datetime import datetime
from langchain_core.messages import HumanMessage

from deep_research.model_config import get_model
from deep_research.usage_tracker import get_tracker
from deep_research.run_logger import get_logger
from deep_research.dataclasses import ObjectivityScore
from deep_research.prompts import (
    fix_report_with_valid_urls_prompt,
    recreate_report_prompt,
    report_summarization_prompt,
)


writer_model = get_model(max_tokens=32000)
summarization_model = get_model("google/gemini-2.5-flash")


def _extract_content_from_message(message: Any) -> str:
    """Extract content from AIMessage or return string representation."""
    return message.content if hasattr(message, "content") else str(message)


def _remove_invalid_urls_from_sources(report: str, invalid_urls: set) -> str:
    """Remove invalid URLs from Sources section."""
    sources_match = re.search(
        r"(###\s*Sources?\s*\n)(.*?)(?=\n###|\Z)", report, re.IGNORECASE | re.DOTALL
    )
    if not sources_match:
        return report

    sources_header = sources_match.group(1)
    sources_text = sources_match.group(2)
    lines = sources_text.split("\n")
    filtered_lines = []

    for line in lines:
        if not any(invalid_url in line for invalid_url in invalid_urls):
            filtered_lines.append(line)
        else:
            print(f"[URL VALIDATION]   - Removed: {line[:100]}...")

    filtered_sources = "\n".join(filtered_lines)
    new_sources_section = sources_header + filtered_sources

    return re.sub(
        r"###\s*Sources?\s*\n.*?(?=\n###|\Z)",
        lambda _match: new_sources_section,
        report,
        flags=re.IGNORECASE | re.DOTALL,
    )


async def fix_report(report_source: str, red_team_evaluation: ObjectivityScore) -> str:
    """
    Clean the report by removing invalid URLs and fixing inconsistent values/claims.

    Args:
        report_source: The original report
        red_team_evaluation: Full red team evaluation including source quality and claim-source consistency

    Returns:
        Cleaned report with invalid URLs removed and inconsistent values/claims fixed
    """
    source_analysis = red_team_evaluation.source_quality
    consistency = red_team_evaluation.claim_source_consistency

    invalid_urls = set(source_analysis.invalid_sources)
    total_urls = source_analysis.total_sources
    valid_urls = total_urls - len(invalid_urls)
    report = _remove_invalid_urls_from_sources(report_source, invalid_urls)

    # Format consistency issues for the prompt
    numerical_issues = consistency.numerical_inconsistencies[:20]  # Limit to 20
    contextual_issues = consistency.contextual_mismatches[:20]  # Limit to 20

    # Format issues as readable text
    numerical_text = (
        "\n".join(
            [
                f"- {issue.get('citation', 'Unknown')}: {issue.get('claim', 'Unknown claim')}\n"
                f"  Claim value: {issue.get('claim_value', 'N/A')}, Source value: {issue.get('source_value', 'N/A')}\n"
                f"  Issue: {issue.get('discrepancy', 'N/A')} (Severity: {issue.get('severity', 'unknown')})"
                for issue in numerical_issues
            ]
        )
        if numerical_issues
        else "None found."
    )

    contextual_text = (
        "\n".join(
            [
                f"- {issue.get('citation', 'Unknown')}: {issue.get('claim', 'Unknown claim')}\n"
                f"  Issue: {issue.get('issue', 'N/A')} (Severity: {issue.get('severity', 'unknown')})"
                for issue in contextual_issues
            ]
        )
        if contextual_issues
        else "None found."
    )

    prompt = fix_report_with_valid_urls_prompt.format(
        valid_urls_count=valid_urls,
        report=report,
        numerical_inconsistencies=numerical_text,
        contextual_mismatches=contextual_text,
    )
    cleaned = await writer_model.ainvoke([HumanMessage(content=prompt)])
    return _extract_content_from_message(cleaned)


async def recreate_report(
    fixed_report: str, research_query: str, recommendations: list[str]
) -> str:
    """
    Recreate the report with the fixed URLs and recommendations.

    Args:
        fixed_report: The fixed report (with invalid URLs removed)
        research_query: The original research query
        recommendations: List of recommendations from red team evaluation

    Returns:
        Recreated report
    """
    prompt = recreate_report_prompt.format(
        fixed_report=fixed_report,
        research_query=research_query,
        recommendations=recommendations,
    )
    recreated = await writer_model.ainvoke([HumanMessage(content=prompt)])
    return _extract_content_from_message(recreated)


async def create_summary(
    main_report: str, red_team_report: str = "", user_query: str = ""
) -> str:
    """
    Create a summary combining main report and red team evaluation.

    Args:
        main_report: The main research report
        red_team_report: The red team evaluation report (optional)
        user_query: The user's query
    Returns:
        Summarized report (max 250 lines)
    """
    if not red_team_report:
        red_team_report = "No red team evaluation available."

    if not user_query:
        user_query = (
            "Summarize the key findings and conclusions from the research report."
        )

    prompt = report_summarization_prompt.format(
        main_report=main_report[:50000],  # Limit to avoid token limits
        red_team_report=red_team_report[:20000],  # Limit to avoid token limits
        user_query=user_query[:20000],  # Limit to avoid token limits
    )

    response = summarization_model.invoke([HumanMessage(content=prompt)])

    tracker = get_tracker()
    token_usage = tracker.track_openai_response(
        response,
        model_name="summarization_model",
        step_name="summary.create",
        metadata={
            "main_report_chars": len(main_report),
            "red_team_chars": len(red_team_report),
        },
    )

    summary = response.content

    # Ensure summary is within 250 lines
    lines = summary.split("\n")
    if len(lines) > 250:
        # Truncate to 250 lines, but try to end at a paragraph boundary
        truncated = lines[:250]
        # Try to find a good stopping point (end of paragraph)
        for i in range(len(truncated) - 1, max(0, len(truncated) - 10), -1):
            if truncated[i].strip() == "":
                truncated = truncated[: i + 1]
                break
        summary = "\n".join(truncated)
        summary += "\n\n[Note: Summary truncated to 250 lines]"

    try:
        logger = get_logger()
        logger.log_step(
            "summary.create",
            "Generated 250-line summary",
            tokens=token_usage,
            extra={"lines": len(lines), "truncated": len(lines) > 250},
            model_label="summarization_model",
        )
    except Exception:
        pass

    return summary


# ===== Evaluation Report Formatting Functions =====


def _format_list_section(title: str, items: list) -> list[str]:
    """Format a list section."""
    if not items:
        return []
    return [f"### {title}", *[f"- {item}" for item in items], ""]


def _format_score_section(score: ObjectivityScore) -> list[str]:
    """Format overall score section."""
    quality_label = (
        "Excellent"
        if score.overall_score > 0.8
        else "Good" if score.overall_score > 0.6 else "Needs Improvement"
    )
    one_sided_label = (
        "High"
        if score.bias_metrics.one_sided_score > 0.6
        else "Moderate" if score.bias_metrics.one_sided_score > 0.4 else "Low"
    )

    return [
        "# Red Team Evaluation Report",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Overall Objectivity Score",
        f"**Score: {score.overall_score:.2%}** ({quality_label})",
        "",
        "## Bias Analysis",
        f"- **One-Sided Score:** {score.bias_metrics.one_sided_score:.2%} ({one_sided_label})",
        f"- **Source Diversity:** {score.bias_metrics.source_diversity_score:.2%}",
        f"- **Quantitative Ratio:** {score.bias_metrics.quantitative_ratio:.2%}",
        "",
    ]


def _format_source_quality_section(score: ObjectivityScore) -> List[str]:
    """Format source quality analysis section."""
    sections = [
        "## Source Quality Analysis",
        f"- **Total Sources:** {score.source_quality.total_sources}",
        f"- **Primary Sources:** {score.source_quality.primary_sources}",
        f"- **Secondary Sources:** {score.source_quality.secondary_sources}",
        f"- **Academic Sources:** {score.source_quality.academic_sources}",
        f"- **Credibility Score:** {score.source_quality.source_credibility_score:.2%}",
        "",
    ]

    # Add claim-source consistency section
    consistency = score.claim_source_consistency
    sections.extend(
        [
            "## Claim-Source Consistency Analysis",
            f"- **Consistency Score:** {consistency.consistency_score:.2%}",
            f"- **Verified Claims:** {consistency.verified_claims_count}",
            f"- **Numerical Inconsistencies:** {len(consistency.numerical_inconsistencies)}",
            f"- **Contextual Mismatches:** {len(consistency.contextual_mismatches)}",
            f"- **Unverifiable Claims:** {len(consistency.unverifiable_claims)}",
            "",
        ]
    )

    return sections


def _format_issues_sections(score: ObjectivityScore) -> List[str]:
    """Format issues sections (citations, claims, gaps, consistency)."""
    sections = []
    sections.extend(
        _format_list_section(
            "Missing Citations", score.source_quality.missing_citations
        )
    )
    sections.extend(
        _format_list_section("Unsupported Claims", score.unsupported_claims)
    )
    sections.extend(
        _format_list_section("Counter-Evidence Gaps", score.counter_evidence_gaps)
    )

    # Add claim-source consistency issues
    consistency = score.claim_source_consistency
    if consistency.numerical_inconsistencies:
        sections.append("### Numerical Inconsistencies")
        for issue in consistency.numerical_inconsistencies[:10]:  # Limit to 10
            claim = issue.get("claim", "Unknown claim")
            citation = issue.get("citation", "")
            claim_val = issue.get("claim_value", "")
            source_val = issue.get("source_value", "")
            discrepancy = issue.get("discrepancy", "")
            severity = issue.get("severity", "unknown")
            sections.append(
                f"- **{severity.upper()}** {citation}: {claim}\n"
                f"  Claim value: {claim_val}, Source value: {source_val}\n"
                f"  Issue: {discrepancy}"
            )
        sections.append("")

    if consistency.contextual_mismatches:
        sections.append("### Contextual Mismatches")
        for issue in consistency.contextual_mismatches[:10]:  # Limit to 10
            claim = issue.get("claim", "Unknown claim")
            citation = issue.get("citation", "")
            issue_desc = issue.get("issue", "")
            severity = issue.get("severity", "unknown")
            sections.append(
                f"- **{severity.upper()}** {citation}: {claim}\n"
                f"  Issue: {issue_desc}"
            )
        sections.append("")

    if consistency.unverifiable_claims:
        sections.append("### Unverifiable Claims")
        for issue in consistency.unverifiable_claims[:10]:  # Limit to 10
            claim = issue.get("claim", "Unknown claim")
            citation = issue.get("citation", "")
            reason = issue.get("reason", "Source content unavailable")
            sections.append(f"- {citation}: {claim}\n  Reason: {reason}")
        sections.append("")

    return sections


def format_evaluation_report(score: ObjectivityScore) -> str:
    """Format the evaluation results as a readable report."""
    report_lines = _format_score_section(score)
    report_lines.extend(
        _format_list_section(
            "Missing Counter-Evidence", score.bias_metrics.missing_counter_evidence
        )
    )
    report_lines.extend(
        _format_list_section(
            "Confirmation Bias Indicators",
            score.bias_metrics.confirmation_bias_indicators,
        )
    )
    report_lines.extend(_format_source_quality_section(score))
    report_lines.extend(_format_issues_sections(score))
    report_lines.extend(
        ["## Recommendations", *[f"{rec}" for rec in score.recommendations], ""]
    )
    return "\n".join(report_lines)


def get_evaluation_summary(score: ObjectivityScore) -> Dict[str, Any]:
    """Get a summary dictionary of the evaluation results."""
    return {
        "overall_score": score.overall_score,
        "bias_metrics": {
            "one_sided_score": score.bias_metrics.one_sided_score,
            "source_diversity_score": score.bias_metrics.source_diversity_score,
            "quantitative_ratio": score.bias_metrics.quantitative_ratio,
            "missing_counter_evidence_count": len(
                score.bias_metrics.missing_counter_evidence
            ),
            "confirmation_bias_indicators_count": len(
                score.bias_metrics.confirmation_bias_indicators
            ),
        },
        "source_quality": {
            "total_sources": score.source_quality.total_sources,
            "primary_sources": score.source_quality.primary_sources,
            "secondary_sources": score.source_quality.secondary_sources,
            "academic_sources": score.source_quality.academic_sources,
            "credibility_score": score.source_quality.source_credibility_score,
            "missing_citations_count": len(score.source_quality.missing_citations),
        },
        "claim_source_consistency": {
            "consistency_score": score.claim_source_consistency.consistency_score,
            "numerical_inconsistencies_count": len(
                score.claim_source_consistency.numerical_inconsistencies
            ),
            "contextual_mismatches_count": len(
                score.claim_source_consistency.contextual_mismatches
            ),
            "unverifiable_claims_count": len(
                score.claim_source_consistency.unverifiable_claims
            ),
            "verified_claims_count": score.claim_source_consistency.verified_claims_count,
        },
        "issues": {
            "unsupported_claims_count": len(score.unsupported_claims),
            "counter_evidence_gaps_count": len(score.counter_evidence_gaps),
        },
        "recommendations_count": len(score.recommendations),
    }
