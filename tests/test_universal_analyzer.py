"""Tests for universal credit analyzer."""

import unittest
from unittest.mock import MagicMock, patch

from credit_research_agent.universal_analyzer import (
    UniversalCreditAnalyzer,
    AnalysisResult,
)
from credit_research_agent.sec_integration import (
    CompanyInfo,
    MetricValue,
    CompanyNotFoundError,
    FilingNotFoundError,
)
from credit_research_agent.config_loader import MetricDefinition


class UniversalAnalyzerTest(unittest.TestCase):
    """Test universal credit analyzer."""

    def setUp(self):
        """Create analyzer instance."""
        self.analyzer = UniversalCreditAnalyzer()

    def test_analysis_result_structure(self):
        """Test AnalysisResult dataclass."""
        result = AnalysisResult(
            company="Tesla Inc.",
            ticker="TSLA",
            theme="leverage_analysis",
            years=[2023, 2024],
            brief="# Tesla - Leverage Analysis",
        )

        self.assertEqual(result.company, "Tesla Inc.")
        self.assertEqual(result.ticker, "TSLA")
        self.assertEqual(result.status, "pending")

    @patch("credit_research_agent.universal_analyzer.SECCompanyLookup")
    def test_lookup_company_success(self, mock_lookup_class):
        """Test company lookup success."""
        mock_lookup = MagicMock()
        mock_lookup_class.return_value = mock_lookup

        mock_company = CompanyInfo(
            name="Apple Inc.",
            cik="0000320193",
            ticker="AAPL",
            sic="3571",
            sector="Technology",
            fiscal_years_available=[2023, 2024],
        )

        mock_lookup.get_cik_by_ticker.return_value = "0000320193"
        mock_lookup.get_company_info.return_value = mock_company

        analyzer = UniversalCreditAnalyzer()
        company_info = analyzer._lookup_company("AAPL")

        self.assertEqual(company_info.name, "Apple Inc.")
        self.assertEqual(company_info.cik, "0000320193")

    @patch("credit_research_agent.universal_analyzer.SECCompanyLookup")
    def test_lookup_company_not_found(self, mock_lookup_class):
        """Test company lookup failure."""
        mock_lookup = MagicMock()
        mock_lookup_class.return_value = mock_lookup

        mock_lookup.get_cik_by_ticker.side_effect = CompanyNotFoundError(
            "Ticker INVALID not found"
        )

        analyzer = UniversalCreditAnalyzer()

        with self.assertRaises(CompanyNotFoundError):
            analyzer._lookup_company("INVALID")

    def test_fetch_10k_data_partial(self):
        """Test 10-K fetch with partial years available."""
        # Mock fetcher
        self.analyzer.fetcher = MagicMock()

        # Only 2023 available, not 2024
        mock_xbrl_2023 = "<xbrl>2023 data</xbrl>"
        self.analyzer.fetcher.fetch_10k_xbrl.side_effect = [
            mock_xbrl_2023,
            FilingNotFoundError("No 10-K for 2024"),
        ]

        xbrl_data = self.analyzer._fetch_10k_data("0000320193", [2023, 2024])

        self.assertIn(2023, xbrl_data)
        self.assertNotIn(2024, xbrl_data)

    def test_fetch_10k_data_none_available(self):
        """Test 10-K fetch when no filings available."""
        self.analyzer.fetcher = MagicMock()
        self.analyzer.fetcher.fetch_10k_xbrl.side_effect = FilingNotFoundError(
            "No 10-K found"
        )

        with self.assertRaises(FilingNotFoundError):
            self.analyzer._fetch_10k_data("0000320193", [2023, 2024])

    def test_extract_metrics_from_companyfacts(self):
        """Test metric extraction from SEC companyfacts."""
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "DebtAndFinancingArrangementsAmount": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2024-02-01",
                                    "end": "2023-12-31",
                                    "val": 50000000000,
                                }
                            ]
                        }
                    }
                }
            }
        }

        self.analyzer.config_loader = MagicMock()
        self.analyzer.config_loader.get_risk_theme.return_value = {
            "metrics": ["total_debt"],
        }
        self.analyzer.config_loader.load_metrics.return_value = {
            "total_debt": MetricDefinition(
                name="total_debt",
                description="Total debt",
                xbrl_selectors=[
                    {"concept": "DebtAndFinancingArrangementsAmount"}
                ],
            )
        }

        metrics = self.analyzer._extract_metrics(
            companyfacts, "leverage_analysis", [2023]
        )

        self.assertIn(2023, metrics)
        self.assertGreater(len(metrics[2023]), 0)

    def test_analyze_error_handling(self):
        """Test analyze method error handling."""
        self.analyzer.lookup = MagicMock()
        self.analyzer.lookup.get_cik_by_ticker.side_effect = CompanyNotFoundError(
            "Company not found"
        )
        self.analyzer.lookup.resolve_company_query.return_value = None

        result = self.analyzer.analyze("INVALID", "leverage_analysis")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)
        self.assertIn("Company Resolution Notice", result.brief)
        self.assertIn("SEC ticker/CIK: not resolved", result.brief)
        self.assertIn("No credit conclusions", result.brief)
        self.assertIn("lookup_company", [s["step"] for s in result.trace])

    def test_analyze_partial_failure(self):
        """Test analyze with partial data availability."""
        self.analyzer.lookup = MagicMock()
        self.analyzer.fetcher = MagicMock()

        # Mock successful lookup
        mock_company = CompanyInfo(
            name="Tesla Inc.",
            cik="0001318605",
            ticker="TSLA",
            sic="3711",
            sector="Manufacturing",
            fiscal_years_available=[2023],
        )
        self.analyzer.lookup.get_cik_by_ticker.return_value = "0001318605"
        self.analyzer.lookup.get_company_info.return_value = mock_company

        self.analyzer.fetcher.fetch_companyfacts.return_value = {
            "entityName": "Tesla Inc.",
            "facts": {},
        }

        # Mock parser
        self.analyzer.parser = MagicMock()
        self.analyzer.parser.extract_metrics_from_companyfacts.return_value = {
            "total_debt": MetricValue(
                metric_name="total_debt",
                value=100.0,
                unit="USD millions",
                fiscal_year=2023,
                xbrl_concept="us-gaap:Debt",
                source="XBRL",
            ),
        }

        # Mock brief generator
        self.analyzer.brief_generator = MagicMock()
        self.analyzer.brief_generator.generate_brief.return_value = (
            "# Tesla - Leverage Brief"
        )

        # Mock config loader
        self.analyzer.config_loader = MagicMock()
        self.analyzer.config_loader.get_risk_theme.return_value = {
            "metrics": ["total_debt"],
        }
        self.analyzer.config_loader.load_metrics.return_value = {
            "total_debt": MetricDefinition(
                name="total_debt",
                description="Total debt",
                xbrl_selectors=[{"concept": "Debt"}],
            )
        }

        result = self.analyzer.analyze("TSLA", "leverage_analysis", [2023, 2024])

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.error)
        self.assertEqual(result.company, "Tesla Inc.")
        self.assertIn(2023, result.metrics)
        self.assertEqual(result.brief, "# Tesla - Leverage Brief")
        self.analyzer.brief_generator.generate_brief.assert_called_once()
        _, _, verified_metrics = self.analyzer.brief_generator.generate_brief.call_args.args
        self.assertEqual(verified_metrics.company_name, "Tesla Inc.")
        self.assertEqual(verified_metrics.fiscal_years, [2023, 2024])
        self.assertEqual(verified_metrics.metrics[2023][0].metric_name, "total_debt")
        self.assertEqual(verified_metrics.metrics[2023][0].status, "verified")


class AnalysisResultTest(unittest.TestCase):
    """Test AnalysisResult dataclass."""

    def test_result_defaults(self):
        """Test default values for AnalysisResult."""
        result = AnalysisResult(
            company="Test",
            ticker="TEST",
            theme="test_theme",
            years=[2023],
            brief="",
        )

        self.assertEqual(result.status, "pending")
        self.assertIsNone(result.error)
        self.assertEqual(result.metrics, {})
        self.assertEqual(result.trace, [])

    def test_result_with_data(self):
        """Test AnalysisResult with full data."""
        metrics = {
            2023: [
                MetricValue(
                    metric_name="total_debt",
                    value=100.0,
                    unit="USD millions",
                    fiscal_year=2023,
                    xbrl_concept="us-gaap:Debt",
                    source="XBRL",
                )
            ]
        }

        trace = [
            {"step": "lookup", "status": "success"},
            {"step": "fetch", "status": "success"},
        ]

        result = AnalysisResult(
            company="Apple",
            ticker="AAPL",
            theme="leverage_analysis",
            years=[2023],
            brief="# Apple Leverage",
            metrics=metrics,
            trace=trace,
            status="success",
        )

        self.assertEqual(result.company, "Apple")
        self.assertEqual(len(result.metrics[2023]), 1)
        self.assertEqual(len(result.trace), 2)
        self.assertEqual(result.status, "success")


if __name__ == "__main__":
    unittest.main()
