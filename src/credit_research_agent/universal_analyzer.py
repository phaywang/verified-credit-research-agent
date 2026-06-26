"""Universal SEC-based credit analysis for any company ticker.

Integrates SEC EDGAR data fetching with M3 ReAct agent and brief generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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
    VerifiedMetricsSet,
)
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
            result.trace.append({
                "step": "lookup_company",
                "status": "success",
                "company": company_info.name,
                "cik": company_info.cik,
            })

            # Step 2: Fetch 10-K data
            logger.info(f"Fetching 10-K data for {years}...")
            result.trace.append({"step": "fetch_10k_data", "status": "starting"})

            xbrl_data = self._fetch_10k_data(company_info.cik, years)
            result.trace.append({
                "step": "fetch_10k_data",
                "status": "success",
                "years_fetched": list(xbrl_data.keys()),
            })

            # Step 3: Parse XBRL and extract metrics
            logger.info("Parsing XBRL and extracting metrics...")
            result.trace.append({"step": "parse_xbrl", "status": "starting"})

            metrics_by_year = self._extract_metrics(
                xbrl_data, risk_theme, years
            )
            result.metrics = metrics_by_year
            result.trace.append({
                "step": "parse_xbrl",
                "status": "success",
                "metrics_extracted": sum(
                    len(m) for m in metrics_by_year.values()
                ),
            })

            # Step 4: Generate brief
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
                "step": "fetch_10k_data",
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

    def _lookup_company(self, ticker: str) -> CompanyInfo:
        """Lookup company by ticker."""
        cik = self.lookup.get_cik_by_ticker(ticker)
        company_info = self.lookup.get_company_info(cik)
        return company_info

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

    def _extract_metrics(
        self,
        xbrl_data: Dict[int, str],
        risk_theme: str,
        years: List[int],
    ) -> Dict[int, List[MetricValue]]:
        """Extract metrics for each year."""
        metrics_by_year: Dict[int, List[MetricValue]] = {}

        # Get metric names for this theme from config
        theme_config = self.config_loader.get_risk_theme(risk_theme)
        metric_names = theme_config.get("metrics", [])

        for year in years:
            if year not in xbrl_data:
                continue

            logger.info(f"Extracting metrics for {year}...")
            xbrl_content = xbrl_data[year]

            # Parse XBRL and extract metrics
            extracted = self.parser.extract_metrics(
                xbrl_content, metric_names, year
            )

            metrics_by_year[year] = list(extracted.values())

        return metrics_by_year

    def _generate_brief(
        self,
        company_name: str,
        risk_theme: str,
        metrics_by_year: Dict[int, List[MetricValue]],
    ) -> str:
        """Generate markdown brief from metrics."""
        # Convert metrics to VerifiedMetricsSet format
        verified_metrics = VerifiedMetricsSet(
            company_name=company_name,
            risk_theme=risk_theme,
            verified_metrics=metrics_by_year,
        )

        # Generate brief using existing generator
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
