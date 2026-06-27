"""Universal SEC-based credit analysis for any company ticker.

Integrates SEC EDGAR data fetching with M3 ReAct agent and brief generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from credit_research_agent.config_loader import ConfigLoader
from credit_research_agent.sec_integration import (
    SECCompanyLookup,
    SEC10KFetcher,
    XBRLParser,
    CompanyInfo,
    MetricValue,
    CompanyNotFoundError,
    FilingNotFoundError,
    sec_company_not_found_explanation,
)
from credit_research_agent.brief_generator import (
    BriefGenerator,
    MetricResult,
    VerifiedMetricsSet,
)
from credit_research_agent.llm_stage_workpaper import generate_stage_workpaper
from credit_research_agent.metric_resolver import MetricResolver
from credit_research_agent.task_generator import TaskGenerator
from credit_research_agent.xbrl_inventory import XBRLFactInventoryBuilder

logger = logging.getLogger(__name__)


CALCULATED_METRIC_DEPENDENCIES = {
    "free_cash_flow": ["operating_cash_flow", "capital_expenditures"],
}


@dataclass
class AnalysisResult:
    """Result of universal company analysis."""
    company: str
    ticker: str
    theme: str
    years: List[int]
    brief: str
    metrics: Dict[int, List[MetricValue]] = field(default_factory=dict)
    stage_workpaper: List[Dict[str, Any]] = field(default_factory=list)
    trace: List[Dict] = field(default_factory=list)
    status: str = "pending"  # pending, success, partial, error
    error: Optional[str] = None


class UniversalCreditAnalyzer:
    """Analyze any SEC-listed company without pre-configuration."""

    def __init__(self):
        """Initialize analyzer with SEC integration components."""
        self.lookup = SECCompanyLookup()
        self.fetcher = SEC10KFetcher()
        self.parser = XBRLParser()
        self.inventory_builder = XBRLFactInventoryBuilder(self.parser)
        self.metric_resolver = MetricResolver()
        self.config_loader = ConfigLoader()
        self.task_generator = TaskGenerator()
        self.brief_generator = BriefGenerator()
        self._last_metric_coverage: Dict[str, Any] = {}

    def analyze(
        self,
        ticker: str,
        risk_theme: str,
        years: Optional[List[int]] = None,
        include_llm_workpaper: bool = False,
    ) -> AnalysisResult:
        """Analyze any SEC company end-to-end.

        Args:
            ticker: Stock ticker (e.g., "AAPL", "TSLA")
            risk_theme: Risk theme (e.g., "leverage_analysis")
            years: Fiscal years to analyze (default: [2023, 2024])

        Returns:
            AnalysisResult with brief, metrics, and trace
        """
        if years is None:
            years = [2023, 2024]

        result = AnalysisResult(
            company="",
            ticker=ticker.upper(),
            theme=risk_theme,
            years=years,
            brief="",
        )

        try:
            # Step 1: Lookup company
            logger.info(f"Looking up {ticker}...")
            result.trace.append({"step": "lookup_company", "status": "starting"})

            company_info = self._lookup_company(ticker)
            result.company = company_info.name
            result.ticker = company_info.ticker or result.ticker
            result.trace.append({
                "step": "lookup_company",
                "status": "success",
                "company": company_info.name,
                "ticker": company_info.ticker,
                "cik": company_info.cik,
            })

            # Step 2: Fetch structured SEC companyfacts
            logger.info("Fetching SEC companyfacts...")
            result.trace.append({"step": "fetch_companyfacts", "status": "starting"})

            companyfacts = self._fetch_companyfacts_data(company_info.cik)
            result.trace.append({
                "step": "fetch_companyfacts",
                "status": "success",
                "entity": companyfacts.get("entityName", company_info.name),
            })

            # Step 3: Parse XBRL and extract metrics
            logger.info("Extracting metrics from SEC companyfacts...")
            result.trace.append({"step": "extract_companyfacts", "status": "starting"})

            metrics_by_year = self._extract_metrics(
                companyfacts, risk_theme, years
            )
            result.metrics = metrics_by_year
            result.trace.append({
                "step": "extract_companyfacts",
                "status": "success",
                "metrics_extracted": sum(
                    len(m) for m in metrics_by_year.values()
                ),
                "metric_coverage": self._last_metric_coverage,
            })

            # Step 4: Generate deterministic verified brief
            logger.info("Generating verified brief...")
            result.trace.append({"step": "generate_brief", "status": "starting"})

            brief = self._generate_brief(
                result.company,
                risk_theme,
                metrics_by_year,
            )
            result.brief = brief
            result.trace.append({
                "step": "generate_brief",
                "status": "success",
                "brief_length": len(brief),
            })

            # Step 5: Optional detailed LLM stage workpaper.
            if include_llm_workpaper:
                logger.info("Generating LLM stage workpaper...")
                result.trace.append({"step": "generate_llm_stage_workpaper", "status": "starting"})
                stage_workpaper = generate_stage_workpaper(
                    company=result.company,
                    ticker=result.ticker,
                    risk_theme=risk_theme,
                    years=years,
                    metrics_by_year=metrics_by_year,
                    deterministic_brief=brief,
                )
                result.stage_workpaper = [stage.to_dict() for stage in stage_workpaper]
                result.trace.append({
                    "step": "generate_llm_stage_workpaper",
                    "status": "success",
                    "stages": len(result.stage_workpaper),
                    "guardrails": [
                        stage.get("guardrail_status")
                        for stage in result.stage_workpaper
                    ],
                })

            result.status = "success"
            logger.info(f"✓ Analysis complete for {ticker}")

        except CompanyNotFoundError as e:
            result.status = "error"
            result.error = str(e)
            result.brief = self._generate_unresolved_company_brief(
                ticker,
                risk_theme,
                years,
                str(e),
            )
            result.trace.append({
                "step": "lookup_company",
                "status": "error",
                "error": str(e),
            })
            logger.error(f"Company not found: {e}")

        except FilingNotFoundError as e:
            result.status = "partial"
            result.error = str(e)
            result.trace.append({
                "step": "fetch_companyfacts",
                "status": "error",
                "error": str(e),
            })
            logger.warning(f"Filing not found: {e}")

        except Exception as e:
            result.status = "error"
            result.error = f"Unexpected error: {e}"
            result.trace.append({
                "step": "unknown",
                "status": "error",
                "error": str(e),
            })
            logger.error(f"Analysis error: {e}", exc_info=True)

        return result

    def _lookup_company(self, company_or_ticker: str) -> CompanyInfo:
        """Lookup company by ticker, company name, or common alias."""
        if hasattr(self.lookup, "resolve_company_query"):
            resolved = self.lookup.resolve_company_query(company_or_ticker)
            if isinstance(resolved, CompanyInfo):
                return resolved
        cik = self.lookup.get_cik_by_ticker(company_or_ticker)
        return self.lookup.get_company_info(cik)

    def _fetch_10k_data(
        self, cik: str, years: List[int]
    ) -> Dict[int, str]:
        """Fetch 10-K XBRL content for each year."""
        xbrl_data: Dict[int, str] = {}

        for year in years:
            try:
                logger.info(f"Fetching 10-K for {year}...")
                xbrl_content = self.fetcher.fetch_10k_xbrl(cik, year)
                xbrl_data[year] = xbrl_content
            except FilingNotFoundError as e:
                logger.warning(f"No 10-K for {year}: {e}")
                # Continue with other years

        if not xbrl_data:
            raise FilingNotFoundError(
                f"No 10-K filings found for any of {years}"
            )

        return xbrl_data

    def _fetch_companyfacts_data(self, cik: str) -> Dict[str, Any]:
        """Fetch structured SEC companyfacts for deterministic metric extraction."""
        return self.fetcher.fetch_companyfacts(cik)

    def _generate_unresolved_company_brief(
        self,
        query: str,
        risk_theme: str,
        years: List[int],
        error: str,
    ) -> str:
        """Generate a professional no-coverage explanation for unresolved companies."""
        explanation = error or sec_company_not_found_explanation(query)
        return "\n".join([
            f"# Company Resolution Notice — {query}",
            "",
            "## Status",
            "",
            "The system could not start SEC companyfacts analysis because the input did not resolve to a unique SEC EDGAR ticker/CIK.",
            "",
            "## Resolution Result",
            "",
            f"- Input received: `{query}`",
            f"- Risk theme requested: `{risk_theme}`",
            f"- Fiscal years requested: {', '.join(str(year) for year in years)}",
            "- SEC ticker/CIK: not resolved",
            "",
            "## Explanation",
            "",
            explanation,
            "",
            "## Recommended Next Steps",
            "",
            "- Try the U.S. exchange ticker if the company is publicly listed in the United States.",
            "- Try the full legal registrant name rather than a brand, product, or subsidiary name.",
            "- If the issuer is non-U.S.-listed, use the relevant local filing source instead of SEC companyfacts.",
            "- If the company is private, SEC companyfacts analysis is not available unless the company has a filing registrant or public parent.",
            "",
            "## Control Note",
            "",
            "No credit conclusions or financial metrics were generated because the entity was not verified against SEC EDGAR metadata.",
        ])

    def _extract_metrics(
        self,
        companyfacts: Dict[str, Any],
        risk_theme: str,
        years: List[int],
    ) -> Dict[int, List[MetricValue]]:
        """Extract metrics for each year from SEC companyfacts."""
        metrics_by_year: Dict[int, List[MetricValue]] = {}

        theme_config = self.config_loader.get_risk_theme(risk_theme)
        metric_names = self._metric_names_for_theme(theme_config)
        extraction_metric_names = self._expand_metric_dependencies(metric_names)
        dependency_metrics = [
            metric_name
            for metric_name in extraction_metric_names
            if metric_name not in metric_names
        ]
        metric_selectors = self._metric_selectors(extraction_metric_names)
        self._last_metric_coverage = {
            "requested_metrics": metric_names,
            "dependency_metrics": dependency_metrics,
            "direct_xbrl_metrics": sorted(metric_selectors.keys()),
            "calculated_metrics": [],
            "available_metrics": [],
            "partial_metrics": [],
            "unavailable_metrics": [],
            "missing_metrics_by_year": {},
            "inventory_summary_by_year": {},
            "metric_resolutions_by_year": {},
            "diagnostics": [],
        }

        for year in years:
            logger.info(f"Extracting metrics for {year}...")
            inventory = self.inventory_builder.build(companyfacts, year)
            self._last_metric_coverage["inventory_summary_by_year"][str(year)] = (
                inventory.summary()
            )

            extracted: Dict[str, MetricValue] = {}
            resolutions = []
            for metric_name in extraction_metric_names:
                if (
                    metric_name in CALCULATED_METRIC_DEPENDENCIES
                    and not metric_selectors.get(metric_name)
                ):
                    resolutions.append(
                        {
                            "metric_name": metric_name,
                            "fiscal_year": year,
                            "status": "calculated_metric",
                            "accepted_concept": None,
                            "selected_fact": None,
                            "candidates": [],
                            "rejected_candidates": [],
                            "decision_basis": "deterministic_calculation_from_dependencies",
                            "requires_review": False,
                        }
                    )
                    continue
                resolution = self.metric_resolver.resolve(
                    metric_name,
                    inventory,
                    metric_selectors.get(metric_name, []),
                )
                resolutions.append(resolution.to_dict())
                if resolution.status != "resolved" or resolution.selected_fact is None:
                    continue
                fact = resolution.selected_fact
                extracted[metric_name] = MetricValue(
                    metric_name=metric_name,
                    value=fact.value,
                    unit=fact.unit,
                    fiscal_year=year,
                    xbrl_concept=fact.concept,
                    source=fact.source,
                )

            self._last_metric_coverage["metric_resolutions_by_year"][str(year)] = (
                resolutions
            )
            metrics_by_year[year] = self._with_calculated_metrics(
                year,
                extracted,
                metric_names,
            )

        available_by_metric: Dict[str, List[int]] = {}
        for year, metrics in metrics_by_year.items():
            for metric in metrics:
                available_by_metric.setdefault(metric.metric_name, []).append(year)

        self._last_metric_coverage["available_metrics"] = sorted(available_by_metric)
        self._last_metric_coverage["partial_metrics"] = sorted(
            metric_name
            for metric_name, covered_years in available_by_metric.items()
            if metric_name in metric_names and len(set(covered_years)) < len(years)
        )
        self._last_metric_coverage["unavailable_metrics"] = [
            metric_name
            for metric_name in metric_names
            if metric_name not in available_by_metric
        ]
        self._last_metric_coverage["diagnostics"] = self._build_metric_coverage_diagnostics(
            companyfacts,
            metric_names,
            metric_selectors,
            years,
            available_by_metric,
        )

        return metrics_by_year

    def _metric_names_for_theme(self, theme_config) -> List[str]:
        """Read metric names from either real config dataclass or legacy test dict."""
        if isinstance(theme_config, dict):
            return theme_config.get("key_metrics") or theme_config.get("metrics", [])
        return list(getattr(theme_config, "key_metrics", []))

    @staticmethod
    def _expand_metric_dependencies(metric_names: List[str]) -> List[str]:
        """Include deterministic source metrics required to calculate requested metrics."""
        expanded = list(metric_names)
        for metric_name in metric_names:
            for dependency in CALCULATED_METRIC_DEPENDENCIES.get(metric_name, []):
                if dependency not in expanded:
                    expanded.append(dependency)
        return expanded

    def _metric_selectors(self, metric_names: List[str]) -> Dict[str, List[str]]:
        """Build metric-to-XBRL concept mapping from configured metric definitions."""
        metrics_config = self.config_loader.load_metrics()
        selectors: Dict[str, List[str]] = {}

        for metric_name in metric_names:
            metric_config = metrics_config.get(metric_name)
            if metric_config is None:
                logger.info("Metric %s is not configured for extraction", metric_name)
                continue

            concepts = []
            for selector in getattr(metric_config, "xbrl_selectors", []):
                concept = selector.get("concept")
                if concept:
                    concepts.append(concept)

            if concepts:
                selectors[metric_name] = concepts

        return selectors

    def _build_metric_coverage_diagnostics(
        self,
        companyfacts: Dict[str, Any],
        metric_names: List[str],
        metric_selectors: Dict[str, List[str]],
        years: List[int],
        available_by_metric: Dict[str, List[int]],
    ) -> List[Dict[str, Any]]:
        """Explain missing or partial metric coverage with XBRL concept discovery."""
        diagnostics = []
        for metric_name in metric_names:
            covered_years = sorted(set(available_by_metric.get(metric_name, [])))
            if len(covered_years) == len(years):
                continue

            configured_concepts = metric_selectors.get(metric_name, [])
            search_terms = self._diagnostic_terms(metric_name, configured_concepts)
            candidates = self.parser.discover_companyfact_concepts(
                companyfacts,
                search_terms,
                years,
            )
            configured_set = {concept.split(":")[-1] for concept in configured_concepts}
            configured_candidates = [
                candidate for candidate in candidates
                if candidate.get("concept") in configured_set
            ]
            related_candidates = [
                candidate for candidate in candidates
                if candidate.get("concept") not in configured_set
            ][:8]
            diagnostics.append(
                {
                    "metric_name": metric_name,
                    "status": "unavailable" if not covered_years else "partial",
                    "covered_years": covered_years,
                    "missing_years": [
                        year for year in years if year not in covered_years
                    ],
                    "configured_concepts": configured_concepts,
                    "configured_concept_facts": configured_candidates,
                    "related_companyfact_candidates": related_candidates,
                    "zero_value_candidates": [
                        candidate for candidate in candidates
                        if candidate.get("has_zero_value")
                    ][:8],
                    "diagnosis": self._coverage_diagnosis_text(
                        metric_name,
                        covered_years,
                        related_candidates,
                    ),
                }
            )
        return diagnostics

    @staticmethod
    def _diagnostic_terms(metric_name: str, configured_concepts: List[str]) -> List[str]:
        """Build broad but bounded companyfacts discovery terms for a metric."""
        terms = {
            token
            for token in metric_name.replace("_", " ").split()
            if len(token) >= 4
        }
        for concept in configured_concepts:
            local = concept.split(":")[-1]
            if "Interest" in local:
                terms.add("interest")
            if "Debt" in local:
                terms.add("debt")
            if "Cash" in local:
                terms.add("cash")
            if "Lease" in local:
                terms.add("lease")
        return sorted(terms)

    @staticmethod
    def _coverage_diagnosis_text(
        metric_name: str,
        covered_years: List[int],
        related_candidates: List[Dict[str, Any]],
    ) -> str:
        """Write a concise user-facing explanation for metric coverage gaps."""
        if related_candidates:
            concepts = ", ".join(
                candidate.get("concept", "") for candidate in related_candidates[:3]
            )
            if covered_years:
                return (
                    f"{metric_name} is partially covered by configured concepts; "
                    f"related SEC companyfacts concepts exist ({concepts}), so the "
                    "gap may reflect a concept change or alternate disclosure tag."
                )
            return (
                f"{metric_name} was not covered by configured concepts, but related "
                f"SEC companyfacts concepts exist ({concepts}); review before using "
                "them in verified conclusions."
            )
        if covered_years:
            return (
                f"{metric_name} is partially covered and no obvious alternate "
                "companyfacts concept was discovered for the missing years."
            )
        return (
            f"{metric_name} has no verified companyfacts value and no obvious "
            "alternate concept in the current discovery scan."
        )

    def _with_calculated_metrics(
        self,
        year: int,
        extracted: Dict[str, MetricValue],
        requested_metrics: List[str],
    ) -> List[MetricValue]:
        """Append deterministic derived metrics when source inputs are verified."""
        metrics = dict(extracted)

        if "free_cash_flow" in requested_metrics and "free_cash_flow" not in metrics:
            operating_cash_flow = metrics.get("operating_cash_flow")
            capital_expenditures = metrics.get("capital_expenditures")
            if (
                operating_cash_flow is not None
                and operating_cash_flow.value is not None
                and capital_expenditures is not None
                and capital_expenditures.value is not None
            ):
                capex_outflow = abs(capital_expenditures.value)
                metrics["free_cash_flow"] = MetricValue(
                    metric_name="free_cash_flow",
                    value=operating_cash_flow.value - capex_outflow,
                    unit=operating_cash_flow.unit,
                    fiscal_year=year,
                    xbrl_concept=(
                        f"calculated:{operating_cash_flow.xbrl_concept}"
                        f"-abs({capital_expenditures.xbrl_concept})"
                    ),
                    source="deterministic_calculation",
                )
                calculated = self._last_metric_coverage.setdefault("calculated_metrics", [])
                if "free_cash_flow" not in calculated:
                    calculated.append("free_cash_flow")

        available = set(metrics)
        missing_for_year = []
        for metric_name in requested_metrics:
            if metric_name not in available:
                missing_for_year.append(metric_name)
        if missing_for_year:
            missing_by_year = self._last_metric_coverage.setdefault("missing_metrics_by_year", {})
            missing_by_year[str(year)] = missing_for_year

        return list(metrics.values())

    def _generate_brief(
        self,
        company_name: str,
        risk_theme: str,
        metrics_by_year: Dict[int, List[MetricValue]],
    ) -> str:
        """Generate markdown brief from metrics."""
        converted_metrics = {
            year: [
                MetricResult(
                    metric_name=metric.metric_name,
                    fiscal_year=metric.fiscal_year,
                    value=metric.value,
                    unit=metric.unit,
                    status="verified" if metric.value is not None else "unsupported",
                    source=metric.source,
                )
                for metric in metrics
            ]
            for year, metrics in metrics_by_year.items()
        }

        verified_metrics = VerifiedMetricsSet(
            company_name=company_name,
            fiscal_years=sorted(metrics_by_year.keys()),
            metrics=converted_metrics,
        )

        brief = self.brief_generator.generate_brief(
            company_name, risk_theme, verified_metrics
        )

        return brief


def demo_analyze():
    """Demo: Analyze multiple companies."""
    analyzer = UniversalCreditAnalyzer()

    # Try analyzing Apple
    print("\n" + "=" * 80)
    print("Analyzing Apple Inc. (AAPL) - Leverage Analysis")
    print("=" * 80)

    result = analyzer.analyze(
        ticker="AAPL",
        risk_theme="leverage_analysis",
        years=[2023, 2024],
    )

    print(f"\nStatus: {result.status}")
    print(f"Company: {result.company}")
    print(f"Ticker: {result.ticker}")
    print(f"Theme: {result.theme}")
    print(f"Years: {result.years}")

    if result.status == "success":
        print(f"\nBrief:\n{result.brief}")
    elif result.error:
        print(f"\nError: {result.error}")

    print(f"\nTrace:")
    for step in result.trace:
        print(f"  - {step}")


if __name__ == "__main__":
    demo_analyze()
