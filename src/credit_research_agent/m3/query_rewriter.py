"""LLM-primary query rewrite role for M3 Phase 3."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from credit_research_agent.m3.bedrock_client import invoke_text
from credit_research_agent.m3.deterministic_tools import query_rewrite_helper


def parse_rewrite_json(text: str) -> Dict[str, Any]:
    """Parse a JSON object from an LLM response."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in rewrite response.")
        cleaned = match.group(0)
    data = json.loads(cleaned)
    required = {"rewritten_query", "reasoning_summary", "target_years", "target_sections"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"Rewrite JSON missing fields: {sorted(missing)}")
    data["fallback_used"] = bool(data.get("fallback_used", False))
    return data


def llm_rewrite_query(
    original_query: str,
    coverage_gaps: List[str],
    *,
    company: str = "Ford",
    years: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Ask the LLM to rewrite a retrieval query; fall back to deterministic helper."""

    years = years or [2023, 2025]
    prompt = f"""
Rewrite the SEC filing retrieval query for a Ford debt/liquidity credit research task.

Original query: {original_query}
Coverage gaps: {coverage_gaps}
Company: {company}
Years: {years}

Return JSON only with:
- rewritten_query
- reasoning_summary
- target_years
- target_sections
- fallback_used false

The rewrite must target the specific missing evidence categories, not a generic broad search.
"""
    result = invoke_text(
        prompt,
        system_prompt=(
            "You are the query rewriter role for an auditable credit research agent. "
            "Return concise JSON only. Do not expose private chain-of-thought."
        ),
        max_tokens=700,
    )
    try:
        return parse_rewrite_json(result.text)
    except Exception:
        return query_rewrite_helper(coverage_gaps, company=company, years=years)
