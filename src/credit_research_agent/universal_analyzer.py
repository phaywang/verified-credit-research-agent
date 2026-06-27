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
)
from credit_research_agent.brief_generator import (
    BriefGenerator,
    MetricResult,
    VerifiedMetricsSet,
)
from credit_research_agent.llm_stage_workpaper import generate_stage_workpaper
from credit_research_agent.task_generator import TaskGenerator

logger = logging.getLogger(__name__)


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
        self.config_loader = ConfigLoader()
        self.task_generator = TaskGenerator()
        self.brief_generator = BriefGenerator()

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
        metric_selectors = self._metric_selectors(metric_names)

        for year in years:
            logger.info(f"Extracting metrics for {year}...")
            extracted = self.parser.extract_metrics_from_companyfacts(
                companyfacts, metric_selectors, year
            )
            metrics_by_year[year] = list(extracted.values())

        return metrics_by_year

    def _metric_names_for_theme(self, theme_config) -> List[str]:
        """Read metric names from either real config dataclass or legacy test dict."""
        if isinstance(theme_config, dict):
            return theme_config.get("key_metrics") or theme_config.get("metrics", [])
        return list(getattr(theme_config, "key_metrics", []))

    def _metric_selectors(self, metric_names: List[str]) -> Dict[str, List[str]]:
        """Build metric-to-XBRL concept mapping from configured metric definitions."""
        metrics_config = self.config_loader.load_metrics()
        selectors: Dict[str, List[str]] = {}

        for metric_name in metric_names:
            metric_config = metrics_config.get(metric_name)
            if metric_config is None:
                logger.warning("No metric mapping configured for %s", metric_name)
                continue

            concepts = []
            for selector in getattr(metric_config, "xbrl_selectors", []):
                concept = selector.get("concept")
                if concept:
                    concepts.append(concept)

            if concepts:
                selectors[metric_name] = concepts

        return selectors

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
