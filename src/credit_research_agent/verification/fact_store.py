"""In-memory fact store with deterministic deduplication preferences."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from credit_research_agent.schemas import NumericFact


_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
_SOURCE_RANK = {"xbrl": 2, "text": 1}


class FactStore:
    """Small fact store for M2a verification."""

    def __init__(self) -> None:
        self._facts_by_id: Dict[str, NumericFact] = {}
        self._facts_by_metric_year: Dict[tuple[str, int], NumericFact] = {}

    def add_facts(self, facts: List[NumericFact]) -> None:
        for fact in facts:
            self._facts_by_id[fact.fact_id] = fact
            key = (fact.metric_name, fact.fiscal_year)
            existing = self._facts_by_metric_year.get(key)
            if existing is None or _fact_rank(fact) > _fact_rank(existing):
                self._facts_by_metric_year[key] = fact

    def get_fact(
        self,
        metric_name: str,
        fiscal_year: int,
    ) -> Optional[NumericFact]:
        return self._facts_by_metric_year.get((metric_name, fiscal_year))

    def get_fact_by_id(self, fact_id: str) -> Optional[NumericFact]:
        return self._facts_by_id.get(fact_id)

    def get_pair(
        self,
        metric_name: str,
        old_year: int,
        new_year: int,
    ) -> Optional[Tuple[NumericFact, NumericFact]]:
        old_fact = self.get_fact(metric_name, old_year)
        new_fact = self.get_fact(metric_name, new_year)
        if old_fact is None or new_fact is None:
            return None
        return old_fact, new_fact

    def all_facts(self) -> List[NumericFact]:
        return list(self._facts_by_id.values())


def _fact_rank(fact: NumericFact) -> tuple[int, int, bool]:
    return (
        _CONFIDENCE_RANK[fact.confidence],
        _SOURCE_RANK[fact.fact_source],
        not fact.review_required,
    )
