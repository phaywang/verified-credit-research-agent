"""M3 deterministic numeric guardrails for LLM-written briefs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


FINANCIAL_NUMBER_RE = re.compile(
    r"(?:\$ ?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:B|billion|million|m)?)"
    r"|(?:[+-]?\d+(?:\.\d+)?%)",
    re.IGNORECASE,
)
VERIFIED_TAG_RE = re.compile(r"\[verified:\s*([A-Za-z0-9_:\-.]+)\]")


@dataclass(frozen=True)
class FinancialNumber:
    text: str
    start: int
    end: int


def extract_financial_numbers(text: str) -> List[FinancialNumber]:
    """Extract financial quantities while ignoring years and generic counts."""

    numbers: List[FinancialNumber] = []
    for match in FINANCIAL_NUMBER_RE.finditer(text):
        token = match.group(0)
        # The regex intentionally requires a currency marker, magnitude word, or percent,
        # so standalone years such as 2023/2025 are not captured.
        numbers.append(FinancialNumber(token, match.start(), match.end()))
    return numbers


def allowed_verified_ids(verified_results: Iterable[Dict[str, Any]] | Dict[str, Any]) -> set[str]:
    if isinstance(verified_results, dict):
        ids: set[str] = set()
        for claim_id, value in verified_results.items():
            if isinstance(value, dict) and value.get("status") == "verified":
                ids.add(str(claim_id))
        return ids
    return {
        str(item.get("claim_id"))
        for item in verified_results
        if item.get("status") == "verified" and item.get("claim_id")
    }


def numeric_guardrail_check(
    brief_text: str,
    verified_results: Optional[Iterable[Dict[str, Any]] | Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Require every financial number in LLM prose to be bound to a verified claim."""

    verified_ids = allowed_verified_ids(verified_results or [])
    blocked: List[Dict[str, Any]] = []
    checked: List[Dict[str, Any]] = []

    for number in extract_financial_numbers(brief_text):
        line_start = brief_text.rfind("\n", 0, number.start) + 1
        line_end = brief_text.find("\n", number.end)
        if line_end == -1:
            line_end = len(brief_text)
        line = brief_text[line_start:line_end]
        tags = set(VERIFIED_TAG_RE.findall(line))
        bound = bool(tags & verified_ids)
        item = {
            "number": number.text,
            "line": line.strip(),
            "verified_tags": sorted(tags),
            "bound_to_verified_claim": bound,
        }
        checked.append(item)
        if not bound:
            blocked.append(item)

    return {
        "severity": "block" if blocked else "pass",
        "financial_numbers_checked": len(checked),
        "blocked_count": len(blocked),
        "blocked_claims": blocked,
        "checked_numbers": checked,
        "reasoning_summary": (
            "Financial quantities require same-line [verified: claim_id] bindings; "
            "standalone years and generic counts are ignored."
        ),
    }


def strip_unverified_financial_lines(
    brief_text: str,
    report: Dict[str, Any],
) -> str:
    """Remove lines containing blocked financial numbers for deterministic repair."""

    blocked_lines = {
        item["line"] for item in report.get("blocked_claims", []) if item.get("line")
    }
    if not blocked_lines:
        return brief_text
    kept = [
        line
        for line in brief_text.splitlines()
        if line.strip() not in blocked_lines
    ]
    kept.append("")
    kept.append(
        "Numeric guardrail note: unverified financial-number lines were removed before finalization."
    )
    return "\n".join(kept).rstrip() + "\n"
