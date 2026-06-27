"""Resolve credit metrics from extracted SEC financial statement line items."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from credit_research_agent.sec_integration import MetricValue
from credit_research_agent.statement_extractor import StatementLineItem


@dataclass
class StatementMetricResolution:
    """Resolution decision for one metric from statement rows."""

    metric_name: str
    fiscal_year: int
    status: str
    metric_value: MetricValue | None = None
    source_item: StatementLineItem | None = None
    rejected_items: List[Dict[str, Any]] = field(default_factory=list)
    decision_basis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "fiscal_year": self.fiscal_year,
            "status": self.status,
            "metric_value": (
                {
                    "metric_name": self.metric_value.metric_name,
                    "value": self.metric_value.value,
                    "unit": self.metric_value.unit,
                    "fiscal_year": self.metric_value.fiscal_year,
                    "xbrl_concept": self.metric_value.xbrl_concept,
                    "source": self.metric_value.source,
                }
                if self.metric_value is not None
                else None
            ),
            "source_item": self.source_item.to_dict() if self.source_item is not None else None,
            "rejected_items": self.rejected_items,
            "decision_basis": self.decision_basis,
        }


class StatementMetricResolver:
    """Resolve metrics using statement type and row-label semantics."""

    def resolve(
        self,
        metric_name: str,
        fiscal_year: int,
        line_items: List[StatementLineItem],
    ) -> StatementMetricResolution:
        candidates = [
            item for item in line_items
            if item.fiscal_year == fiscal_year and item.value is not None
        ]

        if metric_name == "operating_cash_flow":
            return self._resolve_from_rows(
                metric_name,
                fiscal_year,
                candidates,
                self._is_operating_cash_flow,
                "verified_statement_cash_flow_operating_activities",
            )
        if metric_name == "capital_expenditures":
            return self._resolve_from_rows(
                metric_name,
                fiscal_year,
                candidates,
                self._is_capital_expenditure,
                "verified_statement_cash_capex",
                reject_reason=self._capex_reject_reason,
            )
        if metric_name == "dividend_payments":
            return self._resolve_from_rows(
                metric_name,
                fiscal_year,
                candidates,
                self._is_dividend_payment,
                "verified_statement_cash_dividends_paid",
            )
        if metric_name == "interest_expense":
            return self._resolve_from_rows(
                metric_name,
                fiscal_year,
                candidates,
                self._is_interest_expense,
                "verified_statement_interest_expense",
                reject_reason=self._interest_reject_reason,
            )
        if metric_name == "current_debt":
            return self._resolve_current_debt(metric_name, fiscal_year, candidates)
        if metric_name == "long_term_debt":
            return self._resolve_from_rows(
                metric_name,
                fiscal_year,
                candidates,
                self._is_long_term_debt,
                "verified_statement_long_term_debt",
            )
        if metric_name == "cash_and_equivalents":
            return self._resolve_from_rows(
                metric_name,
                fiscal_year,
                candidates,
                self._is_cash_and_equivalents,
                "verified_statement_cash_and_equivalents",
            )

        return StatementMetricResolution(
            metric_name=metric_name,
            fiscal_year=fiscal_year,
            status="statement_metric_not_supported",
            decision_basis="no_statement_resolver_for_metric",
        )

    def _resolve_from_rows(
        self,
        metric_name: str,
        fiscal_year: int,
        candidates: List[StatementLineItem],
        accept,
        decision_basis: str,
        reject_reason=None,
    ) -> StatementMetricResolution:
        accepted = [item for item in candidates if accept(item)]
        if accepted:
            selected = self._choose_best(accepted)
            return StatementMetricResolution(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                status="verified_statement",
                metric_value=self._metric_value(metric_name, selected),
                source_item=selected,
                rejected_items=self._rejected_items(candidates, reject_reason),
                decision_basis=decision_basis,
            )
        return StatementMetricResolution(
            metric_name=metric_name,
            fiscal_year=fiscal_year,
            status="statement_row_not_found",
            rejected_items=self._rejected_items(candidates, reject_reason),
            decision_basis="no_statement_row_matched_metric_semantics",
        )

    def _resolve_current_debt(
        self,
        metric_name: str,
        fiscal_year: int,
        candidates: List[StatementLineItem],
    ) -> StatementMetricResolution:
        """Resolve current debt, aggregating separate current borrowing rows."""
        accepted = [item for item in candidates if self._is_current_debt(item)]
        if not accepted:
            return StatementMetricResolution(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                status="statement_row_not_found",
                decision_basis="no_statement_row_matched_metric_semantics",
            )

        total_rows = [
            item for item in accepted
            if "total" in item.normalized_label and "debt" in item.normalized_label
        ]
        if total_rows:
            selected = self._choose_best(total_rows)
            return StatementMetricResolution(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                status="verified_statement",
                metric_value=self._metric_value(metric_name, selected),
                source_item=selected,
                decision_basis="verified_statement_current_debt_total_row",
            )

        unique: Dict[str, StatementLineItem] = {}
        for item in accepted:
            unique[item.normalized_label] = item
        components = list(unique.values())
        if len(components) == 1:
            selected = components[0]
            return StatementMetricResolution(
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                status="verified_statement",
                metric_value=self._metric_value(metric_name, selected),
                source_item=selected,
                decision_basis="verified_statement_current_debt",
            )

        value = sum(abs(item.value or 0.0) for item in components)
        synthetic = StatementLineItem(
            company=components[0].company,
            ticker=components[0].ticker,
            fiscal_year=fiscal_year,
            statement_type="balance_sheet",
            row_label=" + ".join(item.row_label for item in components),
            normalized_label="aggregated current debt",
            value=value,
            unit=components[0].unit,
            period_end=components[0].period_end,
            column_label=components[0].column_label,
            xbrl_concept="+".join(
                item.xbrl_concept or item.normalized_label for item in components
            ),
            source_url=components[0].source_url,
            accession_number=components[0].accession_number,
            confidence="high" if all(item.confidence == "high" for item in components) else "medium",
        )
        return StatementMetricResolution(
            metric_name=metric_name,
            fiscal_year=fiscal_year,
            status="verified_statement",
            metric_value=self._metric_value(metric_name, synthetic),
            source_item=synthetic,
            decision_basis="verified_statement_current_debt_aggregated_components",
        )

    @staticmethod
    def _metric_value(metric_name: str, item: StatementLineItem) -> MetricValue:
        concept = item.xbrl_concept or item.normalized_label.replace(" ", "_")
        return MetricValue(
            metric_name=metric_name,
            value=item.value,
            unit=item.unit,
            fiscal_year=item.fiscal_year,
            xbrl_concept=f"statement:{concept}",
            source="statement_table",
        )

    @staticmethod
    def _choose_best(items: List[StatementLineItem]) -> StatementLineItem:
        high = [item for item in items if item.confidence == "high"]
        return (high or items)[0]

    @staticmethod
    def _rejected_items(candidates: List[StatementLineItem], reject_reason=None) -> List[Dict[str, Any]]:
        rejected = []
        for item in candidates[:30]:
            reason = reject_reason(item) if reject_reason else ""
            if reason:
                rejected.append(
                    {
                        "row_label": item.row_label,
                        "statement_type": item.statement_type,
                        "xbrl_concept": item.xbrl_concept,
                        "value": item.value,
                        "reason": reason,
                    }
                )
        return rejected[:12]

    @staticmethod
    def _is_operating_cash_flow(item: StatementLineItem) -> bool:
        label = item.normalized_label
        return (
            item.statement_type == "cash_flow_statement"
            and "net cash" in label
            and "operating activities" in label
        )

    @staticmethod
    def _is_capital_expenditure(item: StatementLineItem) -> bool:
        label = item.normalized_label
        if item.statement_type != "cash_flow_statement":
            return False
        if "not yet paid" in label or "incurred" in label:
            return False
        if "lease" in label or "additional paid in capital" in label:
            return False
        if "property and equipment" in label and (
            "purchase" in label or "additions" in label or "acquire" in label
        ):
            return True
        if "capital expenditure" in label and "not yet paid" not in label:
            return True
        return False

    @staticmethod
    def _capex_reject_reason(item: StatementLineItem) -> str:
        label = item.normalized_label
        if "property plant and equipment net" in label or "property and equipment net" in label:
            return "PPE balance is not cash capital expenditure."
        if "not yet paid" in label or "incurred" in label:
            return "Capex incurred but not yet paid is not cash capex outflow."
        if "lease" in label:
            return "Lease obligations are not cash capex outflow."
        if "additional paid in capital" in label:
            return "Additional paid-in capital is equity, not capex."
        return ""

    @staticmethod
    def _is_dividend_payment(item: StatementLineItem) -> bool:
        label = item.normalized_label
        return (
            item.statement_type == "cash_flow_statement"
            and "dividend" in label
            and ("paid" in label or "payment" in label)
            and "per share" not in label
            and "declared" not in label
        )

    @staticmethod
    def _is_interest_expense(item: StatementLineItem) -> bool:
        label = item.normalized_label
        concept = item.xbrl_concept or ""
        return (
            item.statement_type == "income_statement"
            and (
                ("interest expense" in label and "income" not in label)
                or concept in {"InterestExpenseDebt", "InterestExpense", "InterestExpenseNonoperating"}
            )
        )

    @staticmethod
    def _interest_reject_reason(item: StatementLineItem) -> str:
        label = item.normalized_label
        if "lease interest" in label:
            return "Lease-only interest is not total interest expense."
        if "interest paid" in label or "cash paid" in label:
            return "Cash interest paid is not accrual interest expense."
        return ""

    @staticmethod
    def _is_current_debt(item: StatementLineItem) -> bool:
        label = item.normalized_label
        if item.statement_type != "balance_sheet":
            return False
        return (
            "short term debt" in label
            or "current portion" in label and "debt" in label
            or "current maturities" in label and "debt" in label
            or "due within one year" in label and "debt" in label
            or "loans and notes payable" in label
        )

    @staticmethod
    def _is_long_term_debt(item: StatementLineItem) -> bool:
        label = item.normalized_label
        return (
            item.statement_type == "balance_sheet"
            and "long term debt" in label
            and "current" not in label
            and "within one year" not in label
            and "due within one year" not in label
        )

    @staticmethod
    def _is_cash_and_equivalents(item: StatementLineItem) -> bool:
        label = item.normalized_label
        return (
            item.statement_type == "balance_sheet"
            and label == "cash and cash equivalents"
        )
