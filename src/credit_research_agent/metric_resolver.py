"""Deterministic metric resolver over annual XBRL fact inventories."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from credit_research_agent.xbrl_inventory import XBRLFact, XBRLFactInventory


@dataclass
class MetricCandidate:
    """Candidate fact considered for a requested metric."""

    fact: XBRLFact
    classification: str
    accepted: bool
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable candidate metadata."""
        return {
            "concept": self.fact.concept,
            "namespace": self.fact.namespace,
            "value": self.fact.value,
            "unit": self.fact.unit,
            "classification": self.classification,
            "accepted": self.accepted,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass
class MetricResolution:
    """Resolver decision for one metric/year."""

    metric_name: str
    fiscal_year: int
    status: str
    selected_fact: XBRLFact | None = None
    accepted_concept: str | None = None
    candidates: List[MetricCandidate] = field(default_factory=list)
    rejected_candidates: List[MetricCandidate] = field(default_factory=list)
    decision_basis: str = ""
    requires_review: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable resolution metadata."""
        return {
            "metric_name": self.metric_name,
            "fiscal_year": self.fiscal_year,
            "status": self.status,
            "accepted_concept": self.accepted_concept,
            "selected_fact": (
                self.selected_fact.to_dict() if self.selected_fact is not None else None
            ),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "rejected_candidates": [
                candidate.to_dict() for candidate in self.rejected_candidates
            ],
            "decision_basis": self.decision_basis,
            "requires_review": self.requires_review,
        }


class MetricResolver:
    """Resolve configured credit metrics from a complete annual fact inventory."""

    def resolve(
        self,
        metric_name: str,
        inventory: XBRLFactInventory,
        configured_concepts: List[str],
    ) -> MetricResolution:
        """Resolve a metric to an annual fact, with conservative audit metadata."""
        configured_fact = inventory.find_by_concept(configured_concepts)
        if configured_fact is not None:
            candidate = MetricCandidate(
                fact=configured_fact,
                classification="configured_match",
                accepted=True,
                confidence=1.0,
                reason="Matched configured XBRL concept in priority order.",
            )
            return MetricResolution(
                metric_name=metric_name,
                fiscal_year=inventory.fiscal_year,
                status="resolved",
                selected_fact=configured_fact,
                accepted_concept=configured_fact.concept,
                candidates=[candidate],
                decision_basis="configured_concept_match",
            )

        if metric_name == "interest_expense":
            return self._resolve_interest_expense(metric_name, inventory)

        terms = self._terms_for_metric(metric_name, configured_concepts)
        related_facts = inventory.search_concepts(terms)
        rejected = [
            MetricCandidate(
                fact=fact,
                classification="not_auto_resolved",
                accepted=False,
                confidence=0.25,
                reason=(
                    "Related concept found, but no deterministic rule accepts it "
                    "as this metric."
                ),
            )
            for fact in related_facts[:12]
        ]
        return MetricResolution(
            metric_name=metric_name,
            fiscal_year=inventory.fiscal_year,
            status="unresolved",
            rejected_candidates=rejected,
            decision_basis="no_configured_or_safe_alternate_concept",
            requires_review=bool(rejected),
        )

    def _resolve_interest_expense(
        self,
        metric_name: str,
        inventory: XBRLFactInventory,
    ) -> MetricResolution:
        """Resolve interest expense using strict concept semantics."""
        related_facts = inventory.search_concepts(["interest"])
        accepted: List[MetricCandidate] = []
        rejected: List[MetricCandidate] = []

        for fact in related_facts:
            classification, is_accepted, confidence, reason = (
                self._classify_interest_expense_candidate(fact)
            )
            candidate = MetricCandidate(
                fact=fact,
                classification=classification,
                accepted=is_accepted,
                confidence=confidence,
                reason=reason,
            )
            if is_accepted:
                accepted.append(candidate)
            else:
                rejected.append(candidate)

        if len(accepted) == 1:
            selected = accepted[0]
            return MetricResolution(
                metric_name=metric_name,
                fiscal_year=inventory.fiscal_year,
                status="resolved",
                selected_fact=selected.fact,
                accepted_concept=selected.fact.concept,
                candidates=accepted,
                rejected_candidates=rejected,
                decision_basis="safe_interest_expense_alternate",
            )

        if len(accepted) > 1:
            accepted_sorted = sorted(
                accepted,
                key=lambda item: (item.confidence, item.fact.concept),
                reverse=True,
            )
            top_confidence = accepted_sorted[0].confidence
            top = [
                candidate
                for candidate in accepted_sorted
                if candidate.confidence == top_confidence
            ]
            if len(top) == 1:
                selected = top[0]
                return MetricResolution(
                    metric_name=metric_name,
                    fiscal_year=inventory.fiscal_year,
                    status="resolved",
                    selected_fact=selected.fact,
                    accepted_concept=selected.fact.concept,
                    candidates=accepted,
                    rejected_candidates=rejected,
                    decision_basis="highest_confidence_interest_expense_alternate",
                )
            return MetricResolution(
                metric_name=metric_name,
                fiscal_year=inventory.fiscal_year,
                status="ambiguous",
                candidates=accepted,
                rejected_candidates=rejected,
                decision_basis="multiple_safe_interest_expense_candidates",
                requires_review=True,
            )

        return MetricResolution(
            metric_name=metric_name,
            fiscal_year=inventory.fiscal_year,
            status="unresolved",
            rejected_candidates=rejected,
            decision_basis="no_safe_interest_expense_candidate",
            requires_review=bool(rejected),
        )

    @staticmethod
    def _classify_interest_expense_candidate(
        fact: XBRLFact,
    ) -> tuple[str, bool, float, str]:
        """Classify an interest-related fact for interest expense resolution."""
        concept = fact.concept
        lowered = concept.lower()

        if fact.unit and fact.unit != "USD":
            return (
                "not_relevant",
                False,
                0.0,
                "Rejected because the unit is not USD.",
            )

        if concept in {"InterestExpense", "InterestAndDebtExpense"}:
            return (
                "same_metric",
                True,
                0.98,
                "Accepted as a direct interest expense concept.",
            )

        if concept == "InterestExpenseNonoperating":
            return (
                "same_metric",
                True,
                0.95,
                "Accepted as nonoperating interest expense, a common companyfacts alternate.",
            )

        if "paid" in lowered or "payment" in lowered or "payments" in lowered:
            return (
                "cash_flow_proxy",
                False,
                0.35,
                "Rejected because cash interest paid is a cash-flow proxy, not expense.",
            )

        if "lease" in lowered:
            return (
                "narrower_component",
                False,
                0.3,
                "Rejected because lease interest is only a component of total interest expense.",
            )

        if "income" in lowered and "expense" not in lowered:
            return (
                "not_relevant",
                False,
                0.05,
                "Rejected because this is interest income rather than expense.",
            )

        if "tax" in lowered or "noncontrolling" in lowered:
            return (
                "not_relevant",
                False,
                0.05,
                "Rejected because this is not debt interest expense.",
            )

        return (
            "not_auto_resolved",
            False,
            0.2,
            "Related interest concept found, but deterministic rules do not accept it.",
        )

    @staticmethod
    def _terms_for_metric(metric_name: str, configured_concepts: List[str]) -> List[str]:
        """Build conservative concept search terms for a metric."""
        terms = {
            token
            for token in metric_name.replace("_", " ").split()
            if len(token) >= 4
        }
        for concept in configured_concepts:
            local = concept.split(":")[-1]
            for token in ("Debt", "Cash", "Interest", "Dividend", "Assets", "Liabilities"):
                if token in local:
                    terms.add(token.lower())
        return sorted(terms)
