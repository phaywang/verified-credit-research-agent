"""Generic brief generator for multi-company, multi-theme credit research.

Creates polished credit briefs from verified metrics and evidence,
without hardcoding company or theme specifics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from credit_research_agent.config_loader import get_loader


@dataclass
class MetricResult:
    """Result of numeric verification for a single metric."""
    metric_name: str
    fiscal_year: int
    value: Optional[float]
    unit: str
    status: str  # "verified", "unsupported", "low_confidence"
    source: str  # e.g., "XBRL", "text_extraction"
    calculation: Optional[str] = None  # e.g., "debt/equity = 100/50 = 2.0"


@dataclass
class VerifiedMetricsSet:
    """Set of verified metrics for a company and risk theme."""
    company_name: str
    fiscal_years: List[int]
    metrics: Dict[int, List[MetricResult]]  # year → [metrics]
    evidence_summary: str = ""


class BriefGenerator:
    """Generate credit briefs from verified metrics and evidence."""

    def __init__(self):
        self.loader = get_loader()

    def generate_brief(
        self,
        company_name: str,
        risk_theme_id: str,
        verified_metrics: VerifiedMetricsSet,
        evidence_narrative: str = "",
    ) -> str:
        """Generate a credit brief from verified metrics.

        Args:
            company_name: e.g., "Ford Motor Company"
            risk_theme_id: e.g., "leverage_analysis"
            verified_metrics: Set of verified metrics and results
            evidence_narrative: Optional narrative from evidence

        Returns:
            Markdown brief text
        """
        theme = self.loader.get_risk_theme(risk_theme_id)

        brief_parts = [
            f"# {company_name} — {theme.description}",
            "",
            "## Executive Summary",
            "",
            self._generate_summary(verified_metrics, theme.description),
            "",
            "## Credit Read-Through",
            "",
            self._generate_credit_readthrough(verified_metrics, risk_theme_id),
            "",
            "## Key Metrics",
            "",
            self._generate_metrics_section(verified_metrics),
            "",
            "## Verified Changes",
            "",
            self._generate_changes_section(verified_metrics),
            "",
            "## Watch Items for Analyst Review",
            "",
            self._generate_watch_items(verified_metrics, risk_theme_id),
            "",
            "## Verification Basis",
            "",
            self._generate_verification_basis(verified_metrics),
            "",
        ]

        if evidence_narrative:
            brief_parts.extend([
                "## Evidence Analysis",
                "",
                evidence_narrative,
                "",
            ])

        brief_parts.extend([
            "## Limitations",
            "",
            self._generate_limitations(verified_metrics, risk_theme_id),
            "",
            "## Follow-Up Questions",
            "",
            self._generate_follow_up_questions(verified_metrics, risk_theme_id),
            "",
            "## Conclusion",
            "",
            self._generate_conclusion(verified_metrics, risk_theme_id),
            "",
            "---",
            "",
            "*Research conducted using SEC filings with deterministic numeric verification.*",
        ])

        return "\n".join(brief_parts)

    def _generate_credit_readthrough(
        self,
        metrics: VerifiedMetricsSet,
        risk_theme_id: str,
    ) -> str:
        """Generate analyst-style interpretation from verified metric changes."""
        if len(metrics.fiscal_years) < 2:
            return (
                "Only one fiscal year is available, so the work product is limited to "
                "a point-in-time metric read rather than a trend conclusion."
            )

        start_year = min(metrics.fiscal_years)
        end_year = max(metrics.fiscal_years)
        changes = self._change_records(metrics)

        if not changes:
            return (
                f"No common verified metrics are available for both {start_year} and "
                f"{end_year}. The agent therefore withholds directional credit conclusions."
            )

        adverse = []
        favorable = []
        mixed = []

        for change in changes:
            metric_name = change["metric_name"]
            absolute = change["absolute_change"]
            signal = self._credit_signal(metric_name, absolute)
            sentence = (
                f"{metric_name.replace('_', ' ')} moved from "
                f"{self._format_value(change['start_value'], change['unit'])} in {start_year} "
                f"to {self._format_value(change['end_value'], change['unit'])} in {end_year} "
                f"({self._format_signed_value(absolute, change['unit'])}; "
                f"{self._format_percent(change['percent_change'])})."
            )
            if signal == "adverse":
                adverse.append(sentence)
            elif signal == "favorable":
                favorable.append(sentence)
            else:
                mixed.append(sentence)

        lines = [
            f"The verified metric set gives a {risk_theme_id.replace('_', ' ')} read "
            f"for fiscal {start_year} to {end_year}. The interpretation below is limited "
            "to metrics with verified values in both years."
        ]

        if adverse:
            lines.append("")
            lines.append("**Pressure signals**")
            lines.extend(f"- {item}" for item in adverse)
        if favorable:
            lines.append("")
            lines.append("**Supportive signals**")
            lines.extend(f"- {item}" for item in favorable)
        if mixed:
            lines.append("")
            lines.append("**Context-dependent signals**")
            lines.extend(f"- {item}" for item in mixed)

        if adverse and favorable:
            lines.append("")
            lines.append(
                "Overall read: signals are mixed, so the agent avoids a broad upgrade/"
                "deterioration label and points the analyst to the specific metric drivers."
            )
        elif adverse:
            lines.append("")
            lines.append(
                "Overall read: verified metrics lean toward higher credit pressure on this "
                "theme, subject to the limitations below."
            )
        elif favorable:
            lines.append("")
            lines.append(
                "Overall read: verified metrics lean toward lower credit pressure on this "
                "theme, subject to the limitations below."
            )

        return "\n".join(lines)

    def _generate_summary(self, metrics: VerifiedMetricsSet, theme_desc: str) -> str:
        """Generate executive summary from metrics."""
        if len(metrics.fiscal_years) >= 2:
            year1, year2 = metrics.fiscal_years[0], metrics.fiscal_years[-1]
            verified_count = sum(
                1 for year_metrics in metrics.metrics.values()
                for m in year_metrics if m.status == "verified"
            )
            return (
                f"This analysis examines {metrics.company_name}'s {theme_desc} "
                f"for fiscal {year1} vs {year2}. Based on SEC filing analysis, "
                f"{verified_count} numeric metrics have been verified and calculated."
            )
        else:
            return (
                f"This analysis examines {metrics.company_name}'s {theme_desc} "
                f"based on available SEC filing data."
            )

    def _generate_metrics_section(self, metrics: VerifiedMetricsSet) -> str:
        """Generate metrics table."""
        lines = []

        # Group by year
        for year in sorted(metrics.fiscal_years):
            year_metrics = metrics.metrics.get(year, [])
            if not year_metrics:
                continue

            lines.append(f"### Fiscal {year}")
            lines.append("")
            lines.append("| Metric | Value | Status |")
            lines.append("|--------|-------|--------|")

            for metric in year_metrics:
                value_str = f"{metric.value:,.2f}" if metric.value is not None else "N/A"
                if metric.value is not None:
                    value_str = f"{value_str} {metric.unit}"

                status_icon = {
                    "verified": "✓",
                    "unsupported": "✗",
                    "low_confidence": "⚠",
                }.get(metric.status, "?")

                lines.append(
                    f"| {metric.metric_name} | {value_str} | {status_icon} {metric.status} |"
                )

            lines.append("")

        return "\n".join(lines)

    def _generate_changes_section(self, metrics: VerifiedMetricsSet) -> str:
        """Generate deterministic year-over-year change analysis."""
        if len(metrics.fiscal_years) < 2:
            return "At least two fiscal years are required to calculate verified changes."

        start_year = min(metrics.fiscal_years)
        end_year = max(metrics.fiscal_years)
        start_metrics = self._verified_metric_map(metrics, start_year)
        end_metrics = self._verified_metric_map(metrics, end_year)
        common_metric_names = sorted(set(start_metrics) & set(end_metrics))

        if not common_metric_names:
            return (
                f"No metrics have verified values in both {start_year} and {end_year}; "
                "trend conclusions are therefore withheld."
            )

        lines = [
            f"Verified numeric changes from fiscal {start_year} to fiscal {end_year}:",
            "",
            "| Metric | Start | End | Absolute Change | Percent Change | Direction |",
            "|--------|-------|-----|-----------------|----------------|-----------|",
        ]

        notes = []
        for metric_name in common_metric_names:
            start_metric = start_metrics[metric_name]
            end_metric = end_metrics[metric_name]
            if start_metric.value is None or end_metric.value is None:
                continue

            absolute_change = end_metric.value - start_metric.value
            percent_change = None
            if start_metric.value != 0:
                percent_change = absolute_change / abs(start_metric.value) * 100
            direction = self._direction(absolute_change)
            unit = end_metric.unit or start_metric.unit

            lines.append(
                "| "
                f"{metric_name} | "
                f"{self._format_value(start_metric.value, unit)} | "
                f"{self._format_value(end_metric.value, unit)} | "
                f"{self._format_signed_value(absolute_change, unit)} | "
                f"{self._format_percent(percent_change)} | "
                f"{direction} |"
            )

            note = self._analyst_note(metric_name, absolute_change, percent_change)
            if note:
                notes.append(note)

        if notes:
            lines.extend(["", "**Analyst notes**"])
            lines.extend(f"- {note}" for note in notes)

        return "\n".join(lines)

    def _change_records(self, metrics: VerifiedMetricsSet) -> List[Dict[str, Any]]:
        """Return deterministic change records for common verified metrics."""
        if len(metrics.fiscal_years) < 2:
            return []

        start_year = min(metrics.fiscal_years)
        end_year = max(metrics.fiscal_years)
        start_metrics = self._verified_metric_map(metrics, start_year)
        end_metrics = self._verified_metric_map(metrics, end_year)
        records = []

        for metric_name in sorted(set(start_metrics) & set(end_metrics)):
            start_metric = start_metrics[metric_name]
            end_metric = end_metrics[metric_name]
            if start_metric.value is None or end_metric.value is None:
                continue
            absolute_change = end_metric.value - start_metric.value
            percent_change = None
            if start_metric.value != 0:
                percent_change = absolute_change / abs(start_metric.value) * 100
            records.append(
                {
                    "metric_name": metric_name,
                    "start_value": start_metric.value,
                    "end_value": end_metric.value,
                    "absolute_change": absolute_change,
                    "percent_change": percent_change,
                    "unit": end_metric.unit or start_metric.unit,
                }
            )

        return records

    def _generate_watch_items(
        self,
        metrics: VerifiedMetricsSet,
        risk_theme_id: str,
    ) -> str:
        """Generate practical analyst watch items from metric movement."""
        changes = self._change_records(metrics)
        if not changes:
            return (
                "- Confirm whether additional SEC filing sections provide comparable "
                "metrics before making a directional risk call."
            )

        items = []
        for change in changes:
            metric_name = change["metric_name"]
            signal = self._credit_signal(metric_name, change["absolute_change"])
            readable = metric_name.replace("_", " ")

            if signal == "adverse":
                items.append(
                    f"- Review what drove the adverse movement in {readable} and whether "
                    "management identifies a temporary or structural driver."
                )
            elif signal == "favorable":
                items.append(
                    f"- Confirm whether the favorable movement in {readable} is recurring "
                    "or partly timing-related."
                )

        if risk_theme_id == "leverage_analysis":
            items.append("- Compare debt movement with EBITDA, operating income, and interest cost coverage.")
        elif risk_theme_id == "debt_liquidity":
            items.append("- Reconcile cash, credit facility availability, maturities, and management liquidity commentary.")
        elif risk_theme_id == "cash_flow_coverage":
            items.append("- Compare cash generation with required debt service and capital spending.")
        else:
            items.append("- Check whether off-balance-sheet commitments or subsequent events change the risk view.")

        return "\n".join(self._dedupe(items))

    def _generate_verification_basis(self, metrics: VerifiedMetricsSet) -> str:
        """Generate source and coverage table for verified workpaper review."""
        source_counts: Dict[str, int] = {}
        verified_by_metric: Dict[str, set] = {}

        for year, year_metrics in metrics.metrics.items():
            for metric in year_metrics:
                source_counts[metric.source] = source_counts.get(metric.source, 0) + 1
                if metric.status == "verified":
                    verified_by_metric.setdefault(metric.metric_name, set()).add(year)

        lines = [
            "| Check | Result |",
            "|-------|--------|",
            f"| Fiscal years covered | {', '.join(str(year) for year in sorted(metrics.fiscal_years))} |",
            f"| Source mix | {self._format_source_counts(source_counts)} |",
            f"| Verified metrics | {sum(len(year_metrics) for year_metrics in metrics.metrics.values())} extracted metric rows |",
        ]

        if len(metrics.fiscal_years) >= 2:
            required_years = set(metrics.fiscal_years)
            comparable = sorted(
                metric_name
                for metric_name, years in verified_by_metric.items()
                if required_years.issubset(years)
            )
            lines.append(
                "| Verified in both years | "
                f"{', '.join(comparable) if comparable else 'None'} |"
            )

        return "\n".join(lines)

    def _generate_limitations(
        self,
        metrics: VerifiedMetricsSet,
        risk_theme_id: str,
    ) -> str:
        """Generate honest limitations for analyst review."""
        lines = [
            "- This work product uses deterministic SEC/XBRL metric extraction and does not forecast future performance.",
            "- Directional conclusions are limited to metrics verified in the selected fiscal years.",
            "- The brief is not a rating action, investment recommendation, or covenant compliance opinion.",
        ]

        if risk_theme_id == "debt_liquidity":
            lines.append(
                "- Liquidity conclusions require analyst review of credit facility availability, debt maturities, and management commentary."
            )
        elif risk_theme_id == "leverage_analysis":
            lines.append(
                "- Leverage conclusions should be supplemented with EBITDA, lease adjustments, and issuer-specific debt definitions."
            )

        unsupported_count = sum(
            1 for year_metrics in metrics.metrics.values()
            for metric in year_metrics if metric.status != "verified"
        )
        if unsupported_count:
            lines.append(
                f"- {unsupported_count} metric rows were not verified and are not used for trend conclusions."
            )

        return "\n".join(lines)

    def _generate_follow_up_questions(
        self,
        metrics: VerifiedMetricsSet,
        risk_theme_id: str,
    ) -> str:
        """Generate analyst follow-up questions."""
        questions = [
            "- What management explanation supports the largest verified movement?",
            "- Are there material subsequent events after the latest fiscal period?",
            "- Do segment, geography, or financing-entity differences affect metric comparability?",
        ]

        if risk_theme_id == "debt_liquidity":
            questions.insert(
                1,
                "- How much liquidity is immediately available versus restricted, committed, or dependent on market access?",
            )
        elif risk_theme_id == "leverage_analysis":
            questions.insert(
                1,
                "- How do adjusted leverage and coverage ratios compare with rating-agency or lender definitions?",
            )

        if len(metrics.fiscal_years) >= 2:
            start_year = min(metrics.fiscal_years)
            end_year = max(metrics.fiscal_years)
            questions.append(f"- Did accounting policy or presentation changes affect comparability between {start_year} and {end_year}?")

        return "\n".join(questions)

    @staticmethod
    def _verified_metric_map(
        metrics: VerifiedMetricsSet,
        fiscal_year: int,
    ) -> Dict[str, MetricResult]:
        """Return verified metrics for a year keyed by metric name."""
        return {
            metric.metric_name: metric
            for metric in metrics.metrics.get(fiscal_year, [])
            if metric.status == "verified" and metric.value is not None
        }

    @staticmethod
    def _format_value(value: float, unit: str) -> str:
        return f"{value:,.2f} {unit}".strip()

    @staticmethod
    def _format_signed_value(value: float, unit: str) -> str:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:,.2f} {unit}".strip()

    @staticmethod
    def _format_percent(value: Optional[float]) -> str:
        if value is None:
            return "n/a"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"

    @staticmethod
    def _direction(value: float) -> str:
        if value > 0:
            return "increased"
        if value < 0:
            return "decreased"
        return "unchanged"

    @staticmethod
    def _credit_signal(metric_name: str, absolute_change: float) -> str:
        """Classify a metric movement as favorable/adverse/mixed for credit review."""
        name = metric_name.lower()
        if absolute_change == 0:
            return "mixed"

        adverse_when_up = (
            "debt",
            "liabilit",
            "interest",
            "expense",
            "borrow",
            "leverage",
        )
        favorable_when_up = (
            "cash",
            "liquidity",
            "equity",
            "income",
            "earnings",
            "revenue",
            "asset",
            "working_capital",
        )

        if any(token in name for token in adverse_when_up):
            return "adverse" if absolute_change > 0 else "favorable"
        if any(token in name for token in favorable_when_up):
            return "favorable" if absolute_change > 0 else "adverse"
        return "mixed"

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        """Preserve order while removing duplicate analyst notes."""
        seen = set()
        deduped = []
        for item in items:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped

    @staticmethod
    def _format_source_counts(source_counts: Dict[str, int]) -> str:
        if not source_counts:
            return "No source rows"
        return ", ".join(
            f"{source}: {count}"
            for source, count in sorted(source_counts.items())
        )

    @staticmethod
    def _analyst_note(
        metric_name: str,
        absolute_change: float,
        percent_change: Optional[float],
    ) -> str:
        """Create restrained metric-level credit interpretation."""
        readable_name = metric_name.replace("_", " ")
        direction = BriefGenerator._direction(absolute_change)
        percent_text = BriefGenerator._format_percent(percent_change)

        if "debt" in metric_name:
            if absolute_change > 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, which can indicate "
                    "higher leverage or refinancing burden depending on maturity structure."
                )
            if absolute_change < 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, which reduces balance-sheet "
                    "debt burden on this metric."
                )
        if "cash" in metric_name or "liquidity" in metric_name:
            if absolute_change > 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, improving this liquidity "
                    "measure before considering credit-line availability and cash needs."
                )
            if absolute_change < 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, weakening this liquidity "
                    "measure before considering credit-line availability and cash needs."
                )
        if "equity" in metric_name:
            if absolute_change > 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, increasing the equity "
                    "base supporting creditors."
                )
            if absolute_change < 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, reducing the equity "
                    "base supporting creditors."
                )
        if "income" in metric_name or "earnings" in metric_name:
            if absolute_change > 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, supporting internal "
                    "cash generation capacity."
                )
            if absolute_change < 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, pressuring internal "
                    "cash generation capacity."
                )
        if "interest" in metric_name:
            if absolute_change > 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, increasing financing-cost "
                    "pressure."
                )
            if absolute_change < 0:
                return (
                    f"{readable_name} {direction} by {percent_text}, reducing financing-cost "
                    "pressure."
                )
        return ""

    def _generate_conclusion(
        self,
        metrics: VerifiedMetricsSet,
        risk_theme_id: str,
    ) -> str:
        """Generate conclusion from metrics."""
        verified = [
            m for year_metrics in metrics.metrics.values()
            for m in year_metrics if m.status == "verified"
        ]

        if not verified:
            return (
                f"{metrics.company_name}'s {risk_theme_id} position could not be "
                "conclusively assessed due to insufficient verified data."
            )

        theme = self.loader.get_risk_theme(risk_theme_id)

        # Build theme-specific conclusion
        if risk_theme_id == "leverage_analysis":
            return self._leverage_conclusion(metrics, verified)
        elif risk_theme_id == "solvency_assessment":
            return self._solvency_conclusion(metrics, verified)
        elif risk_theme_id == "debt_liquidity":
            return self._debt_liquidity_conclusion(metrics, verified)
        else:
            return (
                f"{metrics.company_name}'s {risk_theme_id} is supported by "
                f"{len(verified)} verified metrics from SEC filings."
            )

    @staticmethod
    def _leverage_conclusion(metrics: VerifiedMetricsSet, verified: List[MetricResult]) -> str:
        """Generate leverage-specific conclusion."""
        debt_metrics = [m for m in verified if "debt" in m.metric_name.lower()]
        equity_metrics = [m for m in verified if "equity" in m.metric_name.lower()]

        if len(metrics.fiscal_years) == 2:
            year1, year2 = min(metrics.fiscal_years), max(metrics.fiscal_years)
            return (
                f"Between {year1} and {year2}, {metrics.company_name}'s leverage position "
                f"is evaluated based on {len(debt_metrics)} debt metrics and "
                f"{len(equity_metrics)} equity metrics, all verified from SEC filings. "
                "The verified changes section above identifies the direction and size of "
                "the debt, equity, earnings, and financing-cost movements that drive the "
                "credit interpretation."
            )
        else:
            return (
                f"{metrics.company_name}'s leverage metrics as of the most recent "
                f"reporting period have been verified from SEC filings ({len(verified)} metrics)."
            )

    @staticmethod
    def _solvency_conclusion(metrics: VerifiedMetricsSet, verified: List[MetricResult]) -> str:
        """Generate solvency-specific conclusion."""
        if len(metrics.fiscal_years) == 2:
            year1, year2 = min(metrics.fiscal_years), max(metrics.fiscal_years)
            return (
                f"{metrics.company_name}'s short-term solvency position from {year1} to {year2} "
                f"is assessed using {len(verified)} verified metrics including current ratios, "
                "quick ratios, and working capital trends. All calculations are deterministic "
                "and based on balance sheet data from SEC filings."
            )
        else:
            return (
                f"{metrics.company_name}'s solvency assessment is supported by "
                f"{len(verified)} verified metrics from the most recent SEC filing."
            )

    @staticmethod
    def _debt_liquidity_conclusion(metrics: VerifiedMetricsSet, verified: List[MetricResult]) -> str:
        """Generate debt/liquidity-specific conclusion."""
        if len(metrics.fiscal_years) == 2:
            year1, year2 = min(metrics.fiscal_years), max(metrics.fiscal_years)
            return (
                f"{metrics.company_name}'s debt and liquidity risk changed from {year1} to {year2}. "
                f"Analysis is based on {len(verified)} verified metrics extracted from SEC filing "
                "data. The conclusion should be read by metric and source: debt, cash, and "
                "liquidity measures may move in different directions, so the brief avoids a "
                "single unsupported improvement/deterioration label."
            )
        else:
            return (
                f"{metrics.company_name}'s debt and liquidity position is characterized by "
                f"{len(verified)} verified metrics from SEC filings."
            )


def brief_from_metrics(
    company_name: str,
    risk_theme_id: str,
    verified_metrics: VerifiedMetricsSet,
    evidence_narrative: str = "",
) -> str:
    """Convenience function to generate a brief."""
    gen = BriefGenerator()
    return gen.generate_brief(company_name, risk_theme_id, verified_metrics, evidence_narrative)
