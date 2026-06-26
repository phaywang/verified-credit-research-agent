"""Targeted query rewrite rules driven by evidence coverage gaps."""

from __future__ import annotations

from typing import List

from credit_research_agent.schemas import EvidenceCoverage, TaskSpec


def rewrite_query(
    task_spec: TaskSpec,
    previous_query: str,
    coverage: EvidenceCoverage,
    iteration: int,
) -> str:
    missing = set(coverage.missing)
    parts: List[str] = ["Ford"]

    missing_text = " ".join(sorted(missing))

    if "2025" in missing_text and "2023" not in missing_text:
        parts.extend(["2025", "10-K"])
    elif "2023" in missing_text and "2025" not in missing_text:
        parts.extend(["2023", "10-K"])
    else:
        parts.extend([str(year) for year in task_spec.years])
        parts.extend(task_spec.filing_types)

    if "debt evidence" in missing_text:
        parts.extend(
            [
                "debt",
                "long-term debt",
                "debt maturities",
                "debt and commitments",
                "company debt excluding Ford Credit",
            ]
        )

    if "liquidity evidence" in missing_text:
        parts.extend(
            [
                "liquidity",
                "capital resources",
                "cash",
                "marketable securities",
                "available liquidity",
            ]
        )

    if "management explanation" in missing:
        parts.extend(
            [
                "management discussion",
                "MD&A",
                "liquidity profile",
                "funding diversified",
                "we manage",
                "reflecting",
            ]
        )

    if "numeric facts" in missing:
        parts.extend(
            [
                "dollars",
                "billion",
                "debt payable",
                "cash",
                "liquidity",
            ]
        )

    if missing == {"2025 evidence"} or "2025 evidence" in missing:
        parts.extend(
            [
                "2025 liquidity capital resources long-term debt committed credit facilities",
            ]
        )
    if missing == {"2023 evidence"} or "2023 evidence" in missing:
        parts.extend(
            [
                "2023 liquidity capital resources long-term debt committed credit facilities",
            ]
        )

    if len(parts) <= 3:
        parts.extend(
            [
                "debt liquidity risk long-term debt liquidity capital resources",
                "credit facilities management discussion",
            ]
        )

    return " ".join(parts)


def rewrite_reason(coverage: EvidenceCoverage) -> str:
    if not coverage.missing:
        return "Evidence coverage was sufficient; no rewrite needed."
    return "Evidence coverage missing: " + ", ".join(coverage.missing) + "."
