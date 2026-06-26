"""Deterministic numeric claim verification."""

from __future__ import annotations

from typing import List

from credit_research_agent.schemas import (
    NumericClaim,
    NumericFact,
    NumericVerificationResult,
)
from credit_research_agent.verification.calculations import (
    calculate_change,
    calculate_percentage_change,
    direction,
)
from credit_research_agent.verification.fact_store import FactStore


def verify_numeric_claim(
    claim: NumericClaim,
    fact_store: FactStore,
) -> NumericVerificationResult:
    """Verify one numeric claim against source facts."""

    old_fact = fact_store.get_fact_by_id(claim.old_fact_id)
    new_fact = fact_store.get_fact_by_id(claim.new_fact_id)

    if old_fact is None or new_fact is None:
        return _result(
            claim,
            "not_enough_data",
            notes=[
                "Missing fact for one or both comparison years.",
            ],
        )

    if old_fact.metric_name != claim.metric_name or new_fact.metric_name != claim.metric_name:
        return _result(
            claim,
            "unsupported",
            old_fact=old_fact,
            new_fact=new_fact,
            notes=[
                "Metric mismatch between claim and source facts.",
            ],
        )

    if old_fact.fiscal_year != claim.old_year or new_fact.fiscal_year != claim.new_year:
        return _result(
            claim,
            "unsupported",
            old_fact=old_fact,
            new_fact=new_fact,
            notes=[
                "Year mismatch between claim and source facts.",
            ],
        )

    if old_fact.confidence != "high" or new_fact.confidence != "high":
        return _result(
            claim,
            "low_confidence",
            old_fact=old_fact,
            new_fact=new_fact,
            notes=[
                "One or both facts are low confidence or review-required.",
            ],
        )

    if old_fact.review_required or new_fact.review_required:
        return _result(
            claim,
            "low_confidence",
            old_fact=old_fact,
            new_fact=new_fact,
            notes=[
                "One or both facts require review.",
            ],
        )

    if old_fact.unit != new_fact.unit:
        return _result(
            claim,
            "inconsistent",
            old_fact=old_fact,
            new_fact=new_fact,
            notes=[
                f"Unit mismatch: {old_fact.unit} vs {new_fact.unit}.",
            ],
        )

    absolute_change = round(calculate_change(old_fact.value, new_fact.value), 6)
    percentage_change = calculate_percentage_change(old_fact.value, new_fact.value)
    change_direction = direction(old_fact.value, new_fact.value)

    return _result(
        claim,
        "verified",
        old_fact=old_fact,
        new_fact=new_fact,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        change_direction=change_direction,
        notes=[
            "Claim verified from high-confidence source facts.",
        ],
    )


def verify_numeric_claims(
    claims: List[NumericClaim],
    fact_store: FactStore,
) -> List[NumericVerificationResult]:
    return [verify_numeric_claim(claim, fact_store) for claim in claims]


def _result(
    claim: NumericClaim,
    status: str,
    *,
    old_fact: NumericFact | None = None,
    new_fact: NumericFact | None = None,
    absolute_change: float | None = None,
    percentage_change: float | None = None,
    change_direction: str | None = None,
    notes: List[str] | None = None,
) -> NumericVerificationResult:
    evidence = []
    for fact in [old_fact, new_fact]:
        if fact is not None:
            evidence.append(
                {
                    "year": fact.fiscal_year,
                    "fact_id": fact.fact_id,
                    "source_chunk_id": fact.source_chunk_id,
                    "source_url": fact.source_url,
                }
            )
    return NumericVerificationResult(
        claim_id=claim.claim_id,
        claim=claim.proposed_statement,
        status=status,  # type: ignore[arg-type]
        metric_name=claim.metric_name,
        old_year=claim.old_year,
        new_year=claim.new_year,
        old_value=old_fact.value if old_fact else None,
        new_value=new_fact.value if new_fact else None,
        unit=old_fact.unit if old_fact else new_fact.unit if new_fact else None,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        direction=change_direction,
        evidence=evidence,
        notes=notes or [],
    )
