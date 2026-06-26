"""Simple M2a evaluation metrics."""

from __future__ import annotations

from typing import List

from credit_research_agent.schemas import (
    EvaluationSummary,
    EvidenceCoverage,
    FinalAnswer,
    NumericVerificationResult,
)


def compute_evaluation_summary(
    final_answer: FinalAnswer,
    verification_results: List[NumericVerificationResult],
    coverage: EvidenceCoverage,
) -> EvaluationSummary:
    verified_count = sum(1 for result in verification_results if result.status == "verified")
    unsupported_count = sum(
        1
        for result in verification_results
        if result.status in {"unsupported", "inconsistent", "not_enough_data", "low_confidence"}
    )
    total = len(verification_results)
    citation_coverage = 0.0
    if final_answer.claims:
        cited = sum(1 for claim in final_answer.claims if claim.citation_chunk_ids)
        citation_coverage = round(cited / len(final_answer.claims), 4)
    numeric_validation_rate = round(verified_count / total, 4) if total else 0.0

    return EvaluationSummary(
        citation_coverage=citation_coverage,
        numeric_validation_rate=numeric_validation_rate,
        unsupported_claim_count=unsupported_count,
        verified_numeric_claim_count=verified_count,
        evidence_coverage_by_year={
            "2023": coverage.has_2023_evidence,
            "2025": coverage.has_2025_evidence,
        },
        evidence_coverage_by_section={
            "debt": coverage.has_debt_evidence,
            "liquidity": coverage.has_liquidity_evidence,
            "management_explanation": coverage.has_management_explanation,
            "numeric_facts": coverage.has_numeric_facts,
        },
    )
