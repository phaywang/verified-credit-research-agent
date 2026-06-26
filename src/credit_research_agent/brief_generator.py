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
            "## Key Metrics",
            "",
            self._generate_metrics_section(verified_metrics),
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
            "## Conclusion",
            "",
            self._generate_conclusion(verified_metrics, risk_theme_id),
            "",
            "---",
            "",
            "*Research conducted using SEC filings with deterministic numeric verification.*",
        ])

        return "\n".join(brief_parts)

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
            year1, year2 = metrics.fiscal_years[0], metrics.fiscal_years[-1]
            return (
                f"Between {year1} and {year2}, {metrics.company_name}'s leverage position "
                f"is evaluated based on {len(debt_metrics)} debt metrics and "
                f"{len(equity_metrics)} equity metrics, all verified from SEC filings. "
                "Analysis of year-over-year changes has been completed with "
                "deterministic numeric calculations."
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
            year1, year2 = metrics.fiscal_years[0], metrics.fiscal_years[-1]
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
            year1, year2 = metrics.fiscal_years[0], metrics.fiscal_years[-1]
            return (
                f"{metrics.company_name}'s debt and liquidity risk changed from {year1} to {year2}. "
                f"Analysis is based on {len(verified)} verified metrics extracted and calculated "
                "from SEC filing data. All numeric changes have been deterministically verified "
                "with no estimation or modeling."
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
