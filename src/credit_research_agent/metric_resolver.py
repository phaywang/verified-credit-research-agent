"""Deterministic metric resolver over annual XBRL fact inventories."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from credit_research_agent.xbrl_inventory import XBRLFact, XBRLFactInventory


SAFE_ALTERNATE_CONCEPTS = {
    "total_debt": {
        "DebtAndFinancingArrangementsAmount": 0.96,
        "DebtLongtermAndShorttermCombinedAmount": 0.96,
        "DebtLongtermAndShorttermCombinedAmountCompanyExcludingFordCredit": 0.95,
        "LongTermDebt": 0.88,
        "DebtInstrumentCarryingAmount": 0.85,
    },
    "current_debt": {
        "DebtCurrent": 0.96,
        "LongTermDebtCurrent": 0.95,
        "CurrentPortionOfLongTermDebt": 0.93,
    },
    "long_term_debt": {
        "LongTermDebtNoncurrent": 0.96,
        "DebtNonCurrent": 0.95,
    },
    "cash_and_equivalents": {
        "CashAndCashEquivalentsAtCarryingValue": 0.98,
        "CashAndCashEquivalentAtCarryingValue": 0.97,
        "Cash": 0.92,
    },
    "shareholders_equity": {
        "StockholdersEquity": 0.98,
        "ShareholdersEquity": 0.96,
    },
    "net_income": {
        "NetIncomeLoss": 0.98,
        "ProfitLoss": 0.94,
        "NetIncome": 0.92,
    },
    "operating_cash_flow": {
        "NetCashProvidedByUsedInOperatingActivities": 0.98,
        "CashFlowFromOperatingActivities": 0.94,
    },
    "capital_expenditures": {
        "PaymentForCapitalExpenditures": 0.98,
        "PaymentsToAcquirePropertyPlantAndEquipment": 0.95,
        "CapitalExpenditures": 0.92,
    },
    "dividend_payments": {
        "PaymentsOfDividends": 0.98,
        "PaymentsOfDividendsCommonStock": 0.95,
        "PaymentsOfDividendsAndDividendEquivalentsOnCommonStockAndRestrictedStockUnits": 0.92,
    },
    "current_assets": {
        "AssetsCurrent": 0.98,
        "CurrentAssets": 0.94,
    },
    "current_liabilities": {
        "LiabilitiesCurrent": 0.98,
        "CurrentLiabilities": 0.94,
    },
    "inventory": {
        "InventoryNet": 0.98,
        "Inventory": 0.94,
    },
}


METRIC_SEARCH_TERMS = {
    "total_debt": ["debt"],
    "current_debt": ["debt", "current", "borrowings"],
    "long_term_debt": ["debt", "noncurrent", "longterm"],
    "cash_and_equivalents": ["cash"],
    "shareholders_equity": ["equity", "stockholders", "shareholders"],
    "net_income": ["income", "profit", "loss"],
    "operating_cash_flow": ["cash", "operating"],
    "capital_expenditures": ["capital", "expenditures", "property", "equipment"],
    "dividend_payments": ["dividend"],
    "current_assets": ["assets", "current"],
    "current_liabilities": ["liabilities", "current"],
    "inventory": ["inventory"],
}


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

        if metric_name in SAFE_ALTERNATE_CONCEPTS:
            return self._resolve_standard_metric(metric_name, inventory)

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

    def _resolve_standard_metric(
        self,
        metric_name: str,
        inventory: XBRLFactInventory,
    ) -> MetricResolution:
        """Resolve common GAAP metrics with metric-specific semantic filters."""
        terms = METRIC_SEARCH_TERMS.get(metric_name, self._terms_for_metric(metric_name, []))
        related_facts = inventory.search_concepts(terms)
        accepted: List[MetricCandidate] = []
        rejected: List[MetricCandidate] = []

        for fact in related_facts:
            classification, is_accepted, confidence, reason = (
                self._classify_standard_candidate(metric_name, fact)
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

        return self._resolution_from_candidates(
            metric_name=metric_name,
            fiscal_year=inventory.fiscal_year,
            accepted=accepted,
            rejected=rejected,
            single_basis="safe_standard_metric_alternate",
            ranked_basis="highest_confidence_standard_metric_alternate",
            ambiguous_basis="multiple_safe_standard_metric_candidates",
            unresolved_basis="no_safe_standard_metric_candidate",
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

        return self._resolution_from_candidates(
            metric_name=metric_name,
            fiscal_year=inventory.fiscal_year,
            accepted=accepted,
            rejected=rejected,
            single_basis="safe_interest_expense_alternate",
            ranked_basis="highest_confidence_interest_expense_alternate",
            ambiguous_basis="multiple_safe_interest_expense_candidates",
            unresolved_basis="no_safe_interest_expense_candidate",
        )

    def _classify_standard_candidate(
        self,
        metric_name: str,
        fact: XBRLFact,
    ) -> tuple[str, bool, float, str]:
        """Classify a candidate for common GAAP metric families."""
        concept = fact.concept
        lowered = concept.lower()

        if fact.unit and fact.unit != "USD":
            return (
                "not_relevant",
                False,
                0.0,
                "Rejected because the unit is not compatible with this metric.",
            )

        safe_concepts = SAFE_ALTERNATE_CONCEPTS.get(metric_name, {})
        if concept in safe_concepts:
            return (
                "same_metric",
                True,
                safe_concepts[concept],
                "Accepted as a safe alternate concept for this metric family.",
            )

        if metric_name == "total_debt":
            if any(token in lowered for token in ("current", "shortterm", "commercialpaper")):
                return (
                    "narrower_component",
                    False,
                    0.3,
                    "Rejected because this is a current or short-term debt component, not total debt.",
                )
            return self._generic_rejection("debt")

        if metric_name == "current_debt":
            if "commercialpaper" in lowered or "shorttermborrowings" in lowered:
                return (
                    "narrower_component",
                    False,
                    0.4,
                    "Rejected because this captures a short-term borrowing component, not all current debt.",
                )
            if "noncurrent" in lowered or lowered == "longtermdebt":
                return (
                    "broader_or_mixed",
                    False,
                    0.2,
                    "Rejected because this is noncurrent or mixed long-term debt.",
                )
            return self._generic_rejection("debt")

        if metric_name == "long_term_debt":
            if "current" in lowered:
                return (
                    "narrower_component",
                    False,
                    0.2,
                    "Rejected because this is current debt, not long-term debt after one year.",
                )
            if concept == "LongTermDebt":
                return (
                    "broader_or_mixed",
                    False,
                    0.45,
                    "Rejected as fallback because LongTermDebt may include current maturities for some issuers.",
                )
            return self._generic_rejection("debt")

        if metric_name == "cash_and_equivalents":
            if "restricted" in lowered:
                return (
                    "broader_or_mixed",
                    False,
                    0.35,
                    "Rejected because restricted cash is not freely available cash and equivalents.",
                )
            if "proceeds" in lowered or "payments" in lowered:
                return (
                    "cash_flow_proxy",
                    False,
                    0.25,
                    "Rejected because this is a cash-flow movement, not ending cash balance.",
                )
            return self._generic_rejection("cash")

        if metric_name == "shareholders_equity":
            if "noncontrollinginterest" in lowered:
                return (
                    "broader_or_mixed",
                    False,
                    0.35,
                    "Rejected because this includes noncontrolling interests.",
                )
            return self._generic_rejection("equity")

        if metric_name == "net_income":
            if "comprehensive" in lowered:
                return (
                    "broader_or_mixed",
                    False,
                    0.3,
                    "Rejected because comprehensive income is broader than net income.",
                )
            if "attributabletononcontrollinginterest" in lowered:
                return (
                    "narrower_component",
                    False,
                    0.2,
                    "Rejected because this is attributable to noncontrolling interest.",
                )
            return self._generic_rejection("income")

        if metric_name == "operating_cash_flow":
            if "continuingoperations" in lowered:
                return (
                    "narrower_component",
                    False,
                    0.45,
                    "Rejected because continuing-operations cash flow may exclude discontinued operations.",
                )
            if "investing" in lowered or "financing" in lowered:
                return (
                    "not_relevant",
                    False,
                    0.05,
                    "Rejected because this is not operating cash flow.",
                )
            return self._generic_rejection("cash flow")

        if metric_name == "capital_expenditures":
            if "proceeds" in lowered or "sale" in lowered:
                return (
                    "cash_flow_proxy",
                    False,
                    0.2,
                    "Rejected because this is asset sale proceeds, not capital expenditure outflow.",
                )
            if "business" in lowered or "acquisition" in lowered:
                return (
                    "broader_or_mixed",
                    False,
                    0.25,
                    "Rejected because this may be business acquisition cash flow, not maintenance/growth capex.",
                )
            return self._generic_rejection("capital expenditure")

        if metric_name == "dividend_payments":
            if "declared" in lowered or "payable" in lowered:
                return (
                    "broader_or_mixed",
                    False,
                    0.35,
                    "Rejected because declared or payable dividends are not cash dividends paid.",
                )
            if "preferred" in lowered:
                return (
                    "narrower_component",
                    False,
                    0.35,
                    "Rejected because preferred dividends are only a component of shareholder distributions.",
                )
            return self._generic_rejection("dividend")

        if metric_name in {"current_assets", "current_liabilities"}:
            expected = "assets" if metric_name == "current_assets" else "liabilities"
            if expected not in lowered:
                return (
                    "not_relevant",
                    False,
                    0.05,
                    f"Rejected because this is not current {expected}.",
                )
            if "noncurrent" in lowered:
                return (
                    "not_relevant",
                    False,
                    0.05,
                    f"Rejected because this is noncurrent {expected}.",
                )
            return self._generic_rejection(expected)

        if metric_name == "inventory":
            if "reserve" in lowered or "allowance" in lowered:
                return (
                    "narrower_component",
                    False,
                    0.25,
                    "Rejected because this is an inventory reserve or allowance, not inventory balance.",
                )
            return self._generic_rejection("inventory")

        return self._generic_rejection(metric_name)

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
    def _generic_rejection(metric_label: str) -> tuple[str, bool, float, str]:
        """Return a standard conservative rejection for related but unsafe facts."""
        return (
            "not_auto_resolved",
            False,
            0.2,
            f"Related {metric_label} concept found, but deterministic rules do not accept it.",
        )

    @staticmethod
    def _resolution_from_candidates(
        metric_name: str,
        fiscal_year: int,
        accepted: List[MetricCandidate],
        rejected: List[MetricCandidate],
        single_basis: str,
        ranked_basis: str,
        ambiguous_basis: str,
        unresolved_basis: str,
    ) -> MetricResolution:
        """Build a resolution from accepted/rejected candidate lists."""
        if len(accepted) == 1:
            selected = accepted[0]
            return MetricResolution(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                status="resolved",
                selected_fact=selected.fact,
                accepted_concept=selected.fact.concept,
                candidates=accepted,
                rejected_candidates=rejected,
                decision_basis=single_basis,
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
                    fiscal_year=fiscal_year,
                    status="resolved",
                    selected_fact=selected.fact,
                    accepted_concept=selected.fact.concept,
                    candidates=accepted,
                    rejected_candidates=rejected,
                    decision_basis=ranked_basis,
                )
            return MetricResolution(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                status="ambiguous",
                candidates=accepted,
                rejected_candidates=rejected,
                decision_basis=ambiguous_basis,
                requires_review=True,
            )

        return MetricResolution(
            metric_name=metric_name,
            fiscal_year=fiscal_year,
            status="unresolved",
            rejected_candidates=rejected,
            decision_basis=unresolved_basis,
            requires_review=bool(rejected),
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
            for token in (
                "Debt",
                "Cash",
                "Interest",
                "Dividend",
                "Assets",
                "Liabilities",
            ):
                if token in local:
                    terms.add(token.lower())
        return sorted(terms)
