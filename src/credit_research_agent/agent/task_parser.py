"""Task parser for the single supported Ford debt/liquidity demo question."""

from __future__ import annotations

from credit_research_agent.config import (
    FORD_CIK,
    FORD_COMPANY,
    FORD_TICKER,
    SUPPORTED_RISK_THEME,
)
from credit_research_agent.schemas import TaskSpec


SUPPORTED_REQUIRED_EVIDENCE = [
    "2023 debt evidence",
    "2025 debt evidence",
    "2023 liquidity evidence",
    "2025 liquidity evidence",
    "management explanation",
    "numeric facts",
]


def parse_task(question: str) -> TaskSpec:
    """Parse the fixed Milestone 1 research question into a task spec."""

    normalized = " ".join(question.lower().replace("’", "'").split())
    required_terms = ["ford", "debt", "liquidity", "2023", "2025"]
    missing_terms = [term for term in required_terms if term not in normalized]
    if missing_terms:
        raise ValueError(
            "Milestone 1 only supports the Ford 2023-to-2025 debt/liquidity "
            f"question. Missing terms: {', '.join(missing_terms)}"
        )

    return TaskSpec(
        company=FORD_COMPANY,
        ticker=FORD_TICKER,
        cik=FORD_CIK,
        years=[2023, 2025],
        filing_types=["10-K"],
        risk_theme=SUPPORTED_RISK_THEME,
        question=question,
        required_evidence=SUPPORTED_REQUIRED_EVIDENCE,
    )

