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

    def test_extracts_calculated_free_cash_flow_without_missing_mapping_warning(self):
        """Calculated metrics should be derived instead of reported as unmapped."""
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "NetCashProvidedByUsedInOperatingActivities": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-01-30",
                                    "end": "2025-09-27",
                                    "val": 111482000000,
                                }
                            ]
                        }
                    },
                    "PaymentForCapitalExpenditures": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-01-30",
                                    "end": "2025-09-27",
                                    "val": 12715000000,
                                }
                            ]
                        }
                    },
                }
            }
        }

        self.analyzer.config_loader = MagicMock()
        self.analyzer.config_loader.get_risk_theme.return_value = {
            "metrics": ["operating_cash_flow", "capital_expenditures", "free_cash_flow"],
        }
        self.analyzer.config_loader.load_metrics.return_value = {
            "operating_cash_flow": MetricDefinition(
                name="operating_cash_flow",
                description="Operating cash flow",
                xbrl_selectors=[
                    {"concept": "NetCashProvidedByUsedInOperatingActivities"}
                ],
            ),
            "capital_expenditures": MetricDefinition(
                name="capital_expenditures",
                description="Capital expenditures",
                xbrl_selectors=[{"concept": "PaymentForCapitalExpenditures"}],
            ),
            "free_cash_flow": MetricDefinition(
                name="free_cash_flow",
                description="Free cash flow",
                formula="operating_cash_flow - capital_expenditures",
            ),
        }

        metrics = self.analyzer._extract_metrics(
            companyfacts, "cash_flow_coverage", [2025]
        )

        by_name = {metric.metric_name: metric for metric in metrics[2025]}
        self.assertIn("free_cash_flow", by_name)
        self.assertEqual(by_name["free_cash_flow"].value, 98767.0)
        self.assertEqual(by_name["free_cash_flow"].source, "deterministic_calculation")
        self.assertIn("free_cash_flow", self.analyzer._last_metric_coverage["calculated_metrics"])
        self.assertNotIn("free_cash_flow", self.analyzer._last_metric_coverage["unavailable_metrics"])

    def test_free_cash_flow_extraction_adds_missing_dependency_metrics(self):
        """Requested calculated metrics should pull deterministic source inputs."""
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "NetCashProvidedByUsedInOperatingActivities": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-01-30",
                                    "end": "2025-12-31",
                                    "val": 1000000000,
                                }
                            ]
                        }
                    },
                    "PaymentsToAcquirePropertyPlantAndEquipment": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-01-30",
                                    "end": "2025-12-31",
                                    "val": 250000000,
                                }
                            ]
                        }
                    },
                }
            }
        }

        self.analyzer.config_loader = MagicMock()
        self.analyzer.config_loader.get_risk_theme.return_value = {
            "metrics": ["operating_cash_flow", "free_cash_flow"],
        }
        self.analyzer.config_loader.load_metrics.return_value = {
            "operating_cash_flow": MetricDefinition(
                name="operating_cash_flow",
                description="Operating cash flow",
                xbrl_selectors=[
                    {"concept": "NetCashProvidedByUsedInOperatingActivities"}
                ],
            ),
            "capital_expenditures": MetricDefinition(
                name="capital_expenditures",
                description="Capital expenditures",
                xbrl_selectors=[
                    {"concept": "PaymentForCapitalExpenditures"}
                ],
            ),
            "free_cash_flow": MetricDefinition(
                name="free_cash_flow",
                description="Free cash flow",
                formula="operating_cash_flow - capital_expenditures",
            ),
        }

        metrics = self.analyzer._extract_metrics(
            companyfacts, "solvency_assessment", [2025]
        )

        by_name = {metric.metric_name: metric for metric in metrics[2025]}
        self.assertEqual(by_name["free_cash_flow"].value, 750.0)
        self.assertEqual(
            self.analyzer._last_metric_coverage["dependency_metrics"],
            ["capital_expenditures"],
        )
        self.assertNotIn(
            "free_cash_flow",
            self.analyzer._last_metric_coverage["unavailable_metrics"],
        )
        resolution = [
            item for item in self.analyzer._last_metric_coverage[
                "metric_resolutions_by_year"
            ]["2025"]
            if item["metric_name"] == "free_cash_flow"
        ][0]
        self.assertEqual(resolution["status"], "calculated_metric")
        self.assertEqual(
            resolution["decision_basis"],
            "deterministic_calculation_from_dependencies",
        )

    def test_records_unavailable_metric_in_coverage(self):
        """Unsupported universal metrics should be structured coverage limits."""
        self.analyzer.config_loader = MagicMock()
        self.analyzer.config_loader.get_risk_theme.return_value = {
            "metrics": ["operating_cash_flow", "total_debt_service"],
        }
        self.analyzer.config_loader.load_metrics.return_value = {
            "operating_cash_flow": MetricDefinition(
                name="operating_cash_flow",
                description="Operating cash flow",
                xbrl_selectors=[
                    {"concept": "NetCashProvidedByUsedInOperatingActivities"}
                ],
            ),
            "total_debt_service": MetricDefinition(
                name="total_debt_service",
                description="Debt service",
                note="Issuer-specific mapping required.",
            ),
        }

        metrics = self.analyzer._extract_metrics(
            {"facts": {"us-gaap": {}}},
            "cash_flow_coverage",
            [2025],
        )

        self.assertEqual(metrics[2025], [])
        self.assertIn(
            "total_debt_service",
            self.analyzer._last_metric_coverage["unavailable_metrics"],
        )

    def test_metric_coverage_diagnoses_alternate_interest_tag(self):
        """Coverage diagnosis should explain concept changes instead of guessing zero."""
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "InterestExpense": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2024-01-29",
                                    "end": "2023-12-31",
                                    "val": 156000000,
                                }
                            ]
                        }
                    },
                    "InterestExpenseNonoperating": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2024,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2025-01-30",
                                    "end": "2024-12-31",
                                    "val": 350000000,
                                },
                                {
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-01-29",
                                    "end": "2025-12-31",
                                    "val": 338000000,
                                },
                            ]
                        }
                    },
                }
            }
        }

        self.analyzer.config_loader = MagicMock()
        self.analyzer.config_loader.get_risk_theme.return_value = {
            "metrics": ["interest_expense"],
        }
        self.analyzer.config_loader.load_metrics.return_value = {
            "interest_expense": MetricDefinition(
                name="interest_expense",
                description="Interest expense",
                xbrl_selectors=[{"concept": "InterestExpense"}],
            ),
        }

        metrics = self.analyzer._extract_metrics(
            companyfacts,
            "leverage_analysis",
            [2023, 2024, 2025],
        )

        self.assertEqual(len(metrics[2023]), 1)
        self.assertEqual(len(metrics[2024]), 1)
        self.assertEqual(len(metrics[2025]), 1)
        coverage = self.analyzer._last_metric_coverage
        self.assertNotIn("interest_expense", coverage["partial_metrics"])
        resolutions_2024 = coverage["metric_resolutions_by_year"]["2024"]
        self.assertEqual(resolutions_2024[0]["status"], "resolved")
        self.assertEqual(
            resolutions_2024[0]["accepted_concept"],
            "InterestExpenseNonoperating",
        )
        self.assertEqual(
            resolutions_2024[0]["decision_basis"],
            "safe_interest_expense_alternate",
        )

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
            "facts": {
                "us-gaap": {
                    "Debt": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2024-01-29",
                                    "end": "2023-12-31",
                                    "val": 100000000,
                                }
                            ]
                        }
                    }
                }
            },
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
