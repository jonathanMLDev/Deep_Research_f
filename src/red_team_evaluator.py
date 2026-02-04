"""
Red Team Evaluation Module

This module provides adversarial evaluation of research results to identify:
- Bias and one-sided arguments
- Missing counter-evidence
- Source quality issues
- Unsupported claims
- Objectivity metrics
"""

import re
from typing import Dict, List, Any, Optional
import json
import asyncio
import aiohttp
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage
from deep_research.model_config import get_model
from deep_research.usage_tracker import get_tracker
from deep_research.run_logger import get_logger
from deep_research.dataclasses import (
    BiasMetrics,
    SourceQualityMetrics,
    ClaimSourceConsistency,
    ObjectivityScore,
)
from deep_research.prompts import (
    red_team_bias_analysis_system_prompt,
    red_team_bias_analysis_prompt,
    red_team_source_analysis_system_prompt,
    red_team_source_analysis_prompt,
    red_team_claim_verification_system_prompt,
    red_team_claim_verification_prompt,
    red_team_claim_source_consistency_system_prompt,
    red_team_claim_source_consistency_prompt,
)


def _get_browser_headers() -> dict:
    """Get browser-like headers to avoid blocking."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def _check_error_page(text_sample: str) -> bool:
    """Check if text sample indicates an error page."""
    text_lower = text_sample.lower()
    error_markers = [
        "<h1>error",
        "<h2>error",
        "error</h1>",
        "error</h2>",
        "page not found",
        "not found</h1>",
        "not found</h2>",
        "<title>404",
        "<h1>404",
        "<h2>404",
        "bad request",
        "invalid request",
    ]
    return any(marker in text_lower for marker in error_markers)


def _is_valid_status_code(status_code: int) -> bool:
    """Check if status code indicates valid response."""
    if 200 <= status_code < 300:
        return True
    elif status_code < 400:
        return True
    elif status_code in (401, 403, 429):
        return True
    return False


async def _check_response_status(response: aiohttp.ClientResponse) -> tuple[bool, int]:
    """Check response status and return (is_valid, status_code)."""
    status_code = response.status
    if 200 <= status_code < 300:
        try:
            text_sample = (await response.text(errors="ignore"))[:4096]
            if _check_error_page(text_sample):
                return False, status_code
        except Exception:
            pass
        return True, status_code
    if _is_valid_status_code(status_code):
        return True, status_code
    return False, status_code


async def _make_url_request(
    clean_url: str, timeout: int, headers: dict
) -> tuple[bool, int]:
    """Make HTTP request and return (is_valid, status_code)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                clean_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
                headers=headers,
            ) as response:
                return await _check_response_status(response)
    except asyncio.TimeoutError:
        return False, 0
    except aiohttp.ClientError:
        return False, 0
    except Exception:
        return False, 0


async def _validate_url_with_retry(
    url: str, timeout: int, max_retries: int, headers: dict
) -> tuple[bool, int]:
    """Validate URL with retry logic."""
    for attempt in range(max_retries + 1):
        is_valid, status_code = await _make_url_request(url, timeout, headers)
        if is_valid or attempt >= max_retries:
            if not is_valid and attempt >= max_retries:
                error_type = "Timeout" if status_code == 0 else "Error"
                print(
                    f"[URL VALIDATION] {error_type} for {url} after {max_retries + 1} attempts"
                )
            return is_valid, status_code
        await asyncio.sleep(1)
    return False, 0


async def validate_url(url: str, timeout: int = 15, max_retries: int = 2) -> tuple:
    """Validate that a URL returns a 200 status code."""
    clean_url = url.rstrip(".,;:!?)")
    parsed = urlparse(clean_url)
    if not parsed.scheme or not parsed.netloc:
        return False, 0

    headers = _get_browser_headers()
    return await _validate_url_with_retry(clean_url, timeout, max_retries, headers)


async def validate_urls(urls: List[str], max_concurrent: int = 10) -> Dict[str, tuple]:
    """
    Validate multiple URLs concurrently.

    Args:
        urls: List of URLs to validate
        max_concurrent: Maximum concurrent requests

    Returns:
        Dictionary mapping URL to (is_valid, status_code)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def validate_with_semaphore(url: str):
        async with semaphore:
            is_valid, status_code = await validate_url(url)
            results[url] = (is_valid, status_code)

    tasks = [validate_with_semaphore(url) for url in urls]
    await asyncio.gather(*tasks, return_exceptions=True)

    return results


def extract_sources_from_report(report: str) -> tuple[List[str], Dict[int, str]]:
    """
    Extract source URLs and their citation numbers from a research report.
    """
    sources = []
    source_map = {}

    # Look for Sources section
    sources_match = re.search(
        r"###\s*Sources?\s*\n(.*?)(?=\n###|\Z)", report, re.IGNORECASE | re.DOTALL
    )
    if sources_match:
        sources_text = sources_match.group(1)

        # Extract URLs from citation format: [N] Title: URL
        citation_pattern = r"\[(\d+)\].*?(https?://[^\s\)]+)"
        for line in sources_text.split("\n"):
            match = re.search(citation_pattern, line)
            if match:
                citation_num = int(match.group(1))
                url = match.group(2).rstrip(".,;:!?)")
                source_map[citation_num] = url

    # Also look for inline URLs in the report
    inline_urls = re.findall(r"https?://[^\s\)]+", report)
    sources.extend(inline_urls)

    # Remove duplicates while preserving order
    seen = set()
    unique_sources = []
    for url in sources:
        # Clean URL (remove trailing punctuation)
        clean_url = url.rstrip(".,;:!?)")
        if clean_url not in seen:
            seen.add(clean_url)
            unique_sources.append(clean_url)

    return unique_sources, source_map


async def fetch_source_content(url: str, timeout: int = 15) -> Optional[str]:
    """
    Fetch content from a source URL for verification.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Text content of the page, or None if fetch fails
    """
    try:
        headers = _get_browser_headers()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
                headers=headers,
            ) as response:
                if response.status == 200:
                    text = await response.text(errors="ignore")
                    # Extract text content (remove HTML tags roughly)
                    # For better extraction, we could use a library, but for now
                    # we'll return a cleaned version
                    text = re.sub(
                        r"<script[^>]*>.*?</script>",
                        "",
                        text,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    text = re.sub(
                        r"<style[^>]*>.*?</style>",
                        "",
                        text,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text)
                    return text[:50000]  # Limit to 50k chars
    except Exception:
        pass
    return None


def _normalize_claim_items(items: list, key: str = "claim") -> list[str]:
    """Normalize claim items to strings."""
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(str(item.get(key, item.get("text", str(item)))))
        else:
            normalized.append(str(item))
    return normalized


def _parse_json_response(content: str) -> Optional[dict]:
    """Parse JSON from response content."""
    try:
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass
    return None


class RedTeamEvaluator:
    """
    Red team evaluator for assessing research objectivity and quality.

    This evaluator acts as an adversarial reviewer, identifying:
    - Potential biases and one-sided arguments
    - Missing counter-evidence or alternative perspectives
    - Source quality issues
    - Unsupported claims
    - Areas needing more quantitative data
    """

    def __init__(self):
        """Initialize the red team evaluator."""
        self.evaluator_model = get_model("google/gemini-2.5-flash")
        self.writer_model = get_model("openai/gpt-5")
        self.tracker = get_tracker()

    def _extract_content_from_message(self, message: Any) -> str:
        """Extract content from AIMessage or return string representation."""
        return message.content if hasattr(message, "content") else str(message)

    async def _run_parallel_evaluations(
        self, report: str, research_query: str, sources: List[str]
    ) -> tuple:
        """Run parallel bias, source, and claim evaluations."""
        bias_analysis = await self._analyze_bias(report, research_query)
        source_analysis = await self._analyze_sources(report, sources)
        claim_verification = await self._verify_claims(report, research_query)
        return bias_analysis, source_analysis, claim_verification

    async def _fetch_source_content_map(
        self, source_map: Dict[int, str], max_concurrent: int = 5
    ) -> Dict[int, str]:
        """
        Fetch content from multiple source URLs concurrently.

        Args:
            source_map: Dictionary mapping citation number to URL
            max_concurrent: Maximum concurrent requests

        Returns:
            Dictionary mapping citation number to source content
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        content_map = {}

        async def fetch_with_semaphore(citation_num: int, url: str):
            async with semaphore:
                content = await fetch_source_content(url)
                if content:
                    content_map[citation_num] = content

        tasks = [
            fetch_with_semaphore(citation_num, url)
            for citation_num, url in source_map.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        return content_map

    async def _verify_claim_source_consistency(
        self, report: str, source_content_map: Dict[int, str]
    ) -> ClaimSourceConsistency:
        """
        Verify consistency between claims and their cited source content,
        with special focus on numerical values.

        Args:
            report: The research report text
            source_content_map: Dictionary mapping citation number to source content

        Returns:
            ClaimSourceConsistency with verification results
        """
        if not source_content_map:
            return ClaimSourceConsistency()

        # Format source content map for prompt
        source_map_text = "\n".join(
            [
                (
                    f"[{citation_num}]: {content[:2000]}..."  # Limit each source to 2000 chars
                    if len(content) > 2000
                    else f"[{citation_num}]: {content}"
                )
                for citation_num, content in sorted(source_content_map.items())
            ]
        )

        prompt = red_team_claim_source_consistency_prompt.format(
            report=report, source_content_map=source_map_text
        )

        response = self.evaluator_model.invoke(
            [
                SystemMessage(content=red_team_claim_source_consistency_system_prompt),
                HumanMessage(content=prompt),
            ]
        )

        self.tracker.track_openai_response(response, model_name="evaluator_model")
        analysis = _parse_json_response(response.content)

        if analysis:
            # Calculate consistency score
            total_issues = len(analysis.get("numerical_inconsistencies", [])) + len(
                analysis.get("contextual_mismatches", [])
            )
            verified_count = analysis.get("verified_claims_count", 0)
            total_claims = verified_count + total_issues

            if total_claims > 0:
                consistency_score = verified_count / total_claims
            else:
                consistency_score = 1.0  # No claims to verify = perfect

            return ClaimSourceConsistency(
                numerical_inconsistencies=analysis.get("numerical_inconsistencies", []),
                contextual_mismatches=analysis.get("contextual_mismatches", []),
                unverifiable_claims=analysis.get("unverifiable_claims", []),
                verified_claims_count=verified_count,
                consistency_score=consistency_score,
            )

        return ClaimSourceConsistency()

    def _create_objectivity_score(
        self,
        overall_score: float,
        bias_analysis: BiasMetrics,
        source_analysis: SourceQualityMetrics,
        claim_verification: Dict[str, List[str]],
        claim_consistency: ClaimSourceConsistency,
        recommendations: List[str],
    ) -> ObjectivityScore:
        """Create ObjectivityScore from analysis results."""
        return ObjectivityScore(
            overall_score=overall_score,
            bias_metrics=bias_analysis,
            source_quality=source_analysis,
            unsupported_claims=claim_verification.get("unsupported", []),
            counter_evidence_gaps=claim_verification.get(
                "missing_counter_evidence", []
            ),
            claim_source_consistency=claim_consistency,
            recommendations=recommendations,
        )

    def _log_evaluation_result(
        self,
        overall_score: float,
        source_analysis: SourceQualityMetrics,
        score: ObjectivityScore,
    ) -> None:
        """Log evaluation result, ignoring errors."""
        try:
            logger = get_logger()
            logger.log_step(
                "red_team.evaluate_report",
                "Red team objectivity score computed",
                extra={
                    "overall_score": overall_score,
                    "total_sources": source_analysis.total_sources,
                    "unsupported_claims": len(score.unsupported_claims),
                },
            )
        except Exception:
            pass

    async def evaluate_report(
        self,
        report: str,
        research_query: str,
    ) -> ObjectivityScore:
        """
        Perform comprehensive red team evaluation of a research report.

        Args:
            report: The research report to evaluate
            research_query: The original research query/question

        Returns:
            ObjectivityScore with detailed metrics and recommendations
        """
        sources, source_map = extract_sources_from_report(report)

        # Run parallel evaluations
        bias_analysis, source_analysis, claim_verification = (
            await self._run_parallel_evaluations(report, research_query, sources or [])
        )

        # Fetch source content and verify claim-source consistency
        source_content_map = await self._fetch_source_content_map(source_map)
        claim_consistency = await self._verify_claim_source_consistency(
            report, source_content_map
        )

        overall_score = self._calculate_objectivity_score(
            bias_analysis, source_analysis, claim_verification, claim_consistency
        )
        recommendations = self._generate_recommendations(
            bias_analysis, source_analysis, claim_verification, claim_consistency
        )

        score = self._create_objectivity_score(
            overall_score,
            bias_analysis,
            source_analysis,
            claim_verification,
            claim_consistency,
            recommendations,
        )

        self._log_evaluation_result(overall_score, source_analysis, score)
        return score

    async def _analyze_bias(self, report: str, query: str) -> BiasMetrics:
        """Analyze the report for bias and one-sided arguments."""
        prompt = red_team_bias_analysis_prompt.format(query=query, report=report)

        response = self.evaluator_model.invoke(
            [
                SystemMessage(content=red_team_bias_analysis_system_prompt),
                HumanMessage(content=prompt),
            ]
        )

        self.tracker.track_openai_response(response, model_name="evaluator_model")
        analysis = _parse_json_response(response.content)

        if analysis:
            return BiasMetrics(
                one_sided_score=analysis.get("one_sided_score", 0.5),
                missing_counter_evidence=analysis.get("missing_counter_evidence", []),
                confirmation_bias_indicators=analysis.get(
                    "confirmation_bias_indicators", []
                ),
                source_diversity_score=analysis.get("source_diversity_score", 0.5),
                quantitative_ratio=analysis.get("quantitative_ratio", 0.5),
            )

        return BiasMetrics()

    def _format_sources_text(self, valid_sources: List[str]) -> str:
        """Format sources list into text for prompt."""
        if valid_sources:
            return "\n".join([f"- {s}" for s in valid_sources])
        return "No sources provided"

    def _parse_source_analysis_response(
        self,
        analysis: dict,
        sources: List[str],
        valid_sources: List[str],
        invalid_sources: List[str],
    ) -> SourceQualityMetrics:
        """Parse analysis response into SourceQualityMetrics."""
        missing_citations = analysis.get("missing_citations", [])
        missing_citations = [
            str(item) if not isinstance(item, str) else item
            for item in missing_citations
        ]

        return SourceQualityMetrics(
            total_sources=int(analysis.get("total_sources", len(sources))),
            valid_sources=len(valid_sources),
            primary_sources=int(analysis.get("primary_sources", 0)),
            secondary_sources=int(analysis.get("secondary_sources", 0)),
            academic_sources=int(analysis.get("academic_sources", 0)),
            source_credibility_score=float(
                analysis.get("source_credibility_score", 0.5)
            ),
            missing_citations=missing_citations,
            invalid_sources=invalid_sources,
        )

    async def _analyze_sources(
        self, report: str, sources: List[str]
    ) -> SourceQualityMetrics:
        """Analyze source quality and credibility."""
        url_validation = await validate_urls(sources)
        valid_sources = [
            url for url, (is_valid, _) in url_validation.items() if is_valid
        ]
        invalid_sources = [url for url in sources if url not in valid_sources]

        sources_text = self._format_sources_text(valid_sources)
        prompt = red_team_source_analysis_prompt.format(
            report=report, sources_text=sources_text
        )

        response = self.evaluator_model.invoke(
            [
                SystemMessage(content=red_team_source_analysis_system_prompt),
                HumanMessage(content=prompt),
            ]
        )

        self.tracker.track_openai_response(response, model_name="evaluator_model")
        analysis = _parse_json_response(response.content)

        if analysis:
            return self._parse_source_analysis_response(
                analysis, sources, valid_sources, invalid_sources
            )

        return SourceQualityMetrics(
            total_sources=len(sources), source_credibility_score=0.5
        )

    async def _verify_claims(self, report: str, query: str) -> Dict[str, List[str]]:
        """Verify claims and identify unsupported assertions."""
        prompt = red_team_claim_verification_prompt.format(query=query, report=report)

        response = self.evaluator_model.invoke(
            [
                SystemMessage(content=red_team_claim_verification_system_prompt),
                HumanMessage(content=prompt),
            ]
        )

        self.tracker.track_openai_response(response, model_name="evaluator_model")
        parsed = _parse_json_response(response.content)

        if parsed:
            result = {
                "unsupported": _normalize_claim_items(
                    parsed.get("unsupported", []), "claim"
                ),
                "missing_counter_evidence": _normalize_claim_items(
                    parsed.get("missing_counter_evidence", []), "gap"
                ),
            }
            return result

        return {"unsupported": [], "missing_counter_evidence": []}

    def _calculate_objectivity_score(
        self,
        bias: BiasMetrics,
        sources: SourceQualityMetrics,
        claims: Dict[str, List[str]],
        claim_consistency: ClaimSourceConsistency,
    ) -> float:
        """Calculate overall objectivity score (0-1, higher = more objective)."""
        # Weighted components
        bias_component = (1.0 - bias.one_sided_score) * 0.35  # Lower one-sided = better
        source_component = sources.source_credibility_score * 0.25
        diversity_component = bias.source_diversity_score * 0.15
        quantitative_component = bias.quantitative_ratio * 0.1
        consistency_component = claim_consistency.consistency_score * 0.15

        # Penalize unsupported claims
        unsupported_penalty = min(len(claims.get("unsupported", [])) * 0.05, 0.15)

        # Penalize numerical inconsistencies and contextual mismatches
        consistency_penalty = min(
            (
                len(claim_consistency.numerical_inconsistencies)
                + len(claim_consistency.contextual_mismatches)
            )
            * 0.03,
            0.15,
        )

        score = (
            bias_component
            + source_component
            + diversity_component
            + quantitative_component
            + consistency_component
        ) * (1.0 - unsupported_penalty - consistency_penalty)

        return max(0.0, min(1.0, score))

    def _add_bias_recommendations(
        self, recommendations: List[str], bias: BiasMetrics
    ) -> None:
        """Add bias-related recommendations."""
        if bias.one_sided_score > 0.6:
            recommendations.append(
                f"⚠️ High one-sided score ({bias.one_sided_score:.2f}): "
                "Consider adding alternative perspectives or counter-arguments."
            )
        if bias.source_diversity_score < 0.5:
            recommendations.append(
                "⚠️ Low source diversity: Include sources from diverse perspectives "
                "and viewpoints."
            )
        if bias.quantitative_ratio < 0.3:
            recommendations.append(
                "⚠️ Low quantitative data: Increase use of specific numbers, "
                "statistics, and measurable metrics."
            )

    def _add_source_recommendations(
        self, recommendations: List[str], sources: SourceQualityMetrics
    ) -> None:
        """Add source quality recommendations."""
        if sources.source_credibility_score < 0.6:
            recommendations.append(
                "⚠️ Source quality concerns: Prioritize primary sources, "
                "official documents, and authoritative publications."
            )

    def _add_claim_recommendations(
        self,
        recommendations: List[str],
        claims: Dict[str, List[str]],
        claim_consistency: ClaimSourceConsistency,
    ) -> None:
        """Add claim verification recommendations."""
        unsupported_count = len(claims.get("unsupported", []))
        if unsupported_count > 0:
            recommendations.append(
                f"⚠️ {unsupported_count} unsupported claim(s) identified: "
                "Add citations or evidence for these assertions."
            )
        missing_counter = len(claims.get("missing_counter_evidence", []))
        if missing_counter > 0:
            recommendations.append(
                f"⚠️ {missing_counter} area(s) need counter-evidence: "
                "Present alternative viewpoints or contradictory evidence."
            )

        # Add consistency-related recommendations
        numerical_issues = len(claim_consistency.numerical_inconsistencies)
        if numerical_issues > 0:
            recommendations.append(
                f"⚠️ {numerical_issues} numerical inconsistency(ies) found: "
                "Verify that numerical values (prices, percentages, counts, etc.) "
                "in claims exactly match their cited sources."
            )
        contextual_issues = len(claim_consistency.contextual_mismatches)
        if contextual_issues > 0:
            recommendations.append(
                f"⚠️ {contextual_issues} contextual mismatch(es) found: "
                "Ensure claims accurately represent the source content, not just "
                "matching numbers but correct interpretation."
            )
        if claim_consistency.consistency_score < 0.8:
            recommendations.append(
                f"⚠️ Claim-source consistency score is {claim_consistency.consistency_score:.1%}: "
                "Review cited claims to ensure they match source content, especially numerical values."
            )

    def _generate_recommendations(
        self,
        bias: BiasMetrics,
        sources: SourceQualityMetrics,
        claims: Dict[str, List[str]],
        claim_consistency: ClaimSourceConsistency,
    ) -> List[str]:
        """Generate actionable recommendations for improving objectivity."""
        recommendations = []
        self._add_bias_recommendations(recommendations, bias)
        self._add_source_recommendations(recommendations, sources)
        self._add_claim_recommendations(recommendations, claims, claim_consistency)

        if not recommendations:
            recommendations.append(
                "✅ Report shows good objectivity and balanced perspective."
            )

        return recommendations


def main():
    url = "https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus"
    is_valid, status_code = asyncio.run(validate_url(url))
    print(is_valid, status_code)
    if is_valid:
        print(f"URL is valid: {url}")
    else:
        print(f"URL is invalid: {url}")
        print(f"Status code: {status_code}")


if __name__ == "__main__":
    main()
