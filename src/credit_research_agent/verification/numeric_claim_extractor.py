"""Deterministic numeric claim proposal from extracted fact pairs."""

from __future__ import annotations

from typing import List

from credit_research_agent.schemas import NumericClaim, NumericFact, TaskSpec
from credit_research_agent.verification.fact_store import FactStore


CLAIM_METRIC_ORDER = [
    "company_debt_excluding_ford_credit",
    "company_debt_payable_within_one_year",
    "company_long_term_debt_payable_after_one_year",
    "company_short_term_borrowings",
    "total_balance_sheet_cash_and_marketable_securities_restricted_cash",
    "company_cash",
    "company_liquidity",
    "ford_credit_net_liquidity_available_for_use",
    "ford_credit_liquidity_sources",
    "ford_credit_committed_capacity",
]


def propose_numeric_claims(
    task_spec: TaskSpec,
    fact_store: FactStore,
) -> List[NumericClaim]:
    """Generate candidate comparison claims for known metrics."""

    old_year, new_year = min(task_spec.years), max(task_spec.years)
    claims: List[NumericClaim] = []
    for metric_name in CLAIM_METRIC_ORDER:
        pair = fact_store.get_pair(metric_name, old_year, new_year)
        if pair is None:
            continue
        old_fact, new_fact = pair
        claims.append(_claim(metric_name, old_year, new_year, old_fact, new_fact))
    return claims


def _claim(
    metric_name: str,
    old_year: int,
    new_year: int,
    old_fact: NumericFact,
    new_fact: NumericFact,
) -> NumericClaim:
    claim_id = f"claim_{metric_name}_{old_year}_{new_year}"
    return NumericClaim(
        claim_id=claim_id,
        metric_name=metric_name,
        claim_type="change_over_time",
        old_year=old_year,
        new_year=new_year,
        old_fact_id=old_fact.fact_id,
        new_fact_id=new_fact.fact_id,
        statement_template=(
            "{display_name} changed from {old_value} in {old_year} "
            "to {new_value} in {new_year}."
        ),
        proposed_statement=(
            f"{old_fact.display_name} changed from ${old_fact.value:.3f}B "
            f"in {old_year} to ${new_fact.value:.3f}B in {new_year}."
        ),
        required_calculations=["absolute_change", "percentage_change"],
    )
