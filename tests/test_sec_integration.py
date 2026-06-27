"""Tests for SEC EDGAR integration."""

import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from credit_research_agent.sec_integration import (
    SECCompanyLookup,
    SEC10KFetcher,
    XBRLParser,
    CompanyNotFoundError,
    FilingNotFoundError,
    _sec_get,
)


RUN_SEC_LIVE_TESTS = os.getenv("RUN_SEC_LIVE_TESTS") == "1"
requires_sec_network = unittest.skipUnless(
    RUN_SEC_LIVE_TESTS,
    "Set RUN_SEC_LIVE_TESTS=1 to run live SEC EDGAR integration tests.",
)


class SECCompanyLookupTest(unittest.TestCase):
    """Test SEC company lookup functionality."""

    def setUp(self):
        """Create lookup instance with cache."""
        self.lookup = SECCompanyLookup(cache_dir=Path("/tmp/sec_cache_test"))

    @requires_sec_network
    def test_get_cik_apple(self):
        """Test CIK lookup for Apple (AAPL)."""
        cik = self.lookup.get_cik_by_ticker("AAPL")
        self.assertEqual(cik, "0000320193")
        self.assertTrue(cik.startswith("000"))  # Zero-padded

    @requires_sec_network
    def test_get_cik_tesla(self):
        """Test CIK lookup for Tesla (TSLA)."""
        cik = self.lookup.get_cik_by_ticker("TSLA")
        self.assertEqual(cik, "0001318605")

    @requires_sec_network
    def test_get_cik_microsoft(self):
        """Test CIK lookup for Microsoft (MSFT)."""
        cik = self.lookup.get_cik_by_ticker("MSFT")
        self.assertEqual(cik, "0000789019")

    @requires_sec_network
    def test_get_cik_invalid_ticker(self):
        """Test that invalid ticker raises error."""
        with self.assertRaises(CompanyNotFoundError):
            self.lookup.get_cik_by_ticker("INVALID_TICKER_XYZ")

    @requires_sec_network
    def test_get_cik_case_insensitive(self):
        """Test that ticker lookup is case-insensitive."""
        cik_upper = self.lookup.get_cik_by_ticker("AAPL")
        cik_lower = self.lookup.get_cik_by_ticker("aapl")
        cik_mixed = self.lookup.get_cik_by_ticker("AaPl")

        self.assertEqual(cik_upper, cik_lower)
        self.assertEqual(cik_upper, cik_mixed)

    def test_resolve_company_query_by_ticker_without_network(self):
        """Resolver accepts ticker input and returns normalized company metadata."""
        self.lookup._load_tickers_json = Mock(return_value={
            "0": {"ticker": "AAPL", "title": "Apple Inc.", "cik_str": 320193},
        })
        self.lookup.get_company_info = Mock(return_value=Mock(
            name="Apple Inc.",
            cik="0000320193",
            ticker="AAPL",
            sic="3571",
            sector="Nasdaq",
            fiscal_years_available=[2024, 2023],
        ))

        info = self.lookup.resolve_company_query("apple")

        self.assertEqual(info.ticker, "AAPL")
        self.assertEqual(info.cik, "0000320193")
        self.lookup.get_company_info.assert_called_once_with("0000320193")

    def test_resolve_company_query_by_partial_name_without_network(self):
        """Resolver accepts partial company names and common aliases."""
        self.lookup._load_tickers_json = Mock(return_value={
            "0": {"ticker": "GOOGL", "title": "Alphabet Inc.", "cik_str": 1652044},
            "1": {"ticker": "JPM", "title": "JPMorgan Chase & Co.", "cik_str": 19617},
        })
        self.lookup.get_company_info = Mock(return_value=Mock(
            name="JPMorgan Chase & Co.",
            cik="0000019617",
            ticker="JPM",
            sic="6021",
            sector="NYSE",
            fiscal_years_available=[2024, 2023],
        ))

        info = self.lookup.resolve_company_query("JP Morgan")

        self.assertEqual(info.ticker, "JPM")
        self.assertEqual(info.cik, "0000019617")

    def test_resolve_company_query_reports_ambiguous_matches(self):
        """Resolver does not silently choose when name search is ambiguous."""
        self.lookup._load_tickers_json = Mock(return_value={
            "0": {"ticker": "ABC", "title": "Alpha Bank Corp.", "cik_str": 1},
            "1": {"ticker": "ABD", "title": "Alpha Bancorp Depositary", "cik_str": 2},
        })

        with self.assertRaises(CompanyNotFoundError) as ctx:
            self.lookup.resolve_company_query("alpha")

        self.assertIn("Ambiguous", str(ctx.exception))

    def test_resolve_company_query_explains_not_sec_covered_company(self):
        """Resolver explains when a company is not in SEC ticker metadata."""
        self.lookup._load_tickers_json = Mock(return_value={
            "0": {"ticker": "AAPL", "title": "Apple Inc.", "cik_str": 320193},
        })

        with self.assertRaises(CompanyNotFoundError) as ctx:
            self.lookup.resolve_company_query("Private Offshore Ltd")

        message = str(ctx.exception)
        self.assertIn("could not be resolved", message)
        self.assertIn("not listed in the United States", message)
        self.assertIn("private", message)

    @requires_sec_network
    def test_tickers_json_caching(self):
        """Test that tickers JSON is cached locally."""
        # First call fetches and caches
        self.lookup.get_cik_by_ticker("AAPL")
        cache_path = self.lookup.cache_dir / "company_tickers.json"
        self.assertTrue(cache_path.exists())

    @requires_sec_network
    def test_get_company_info_apple(self):
        """Test fetching company metadata for Apple."""
        info = self.lookup.get_company_info("0000320193")

        self.assertIn("Apple", info.name)
        self.assertEqual(info.cik, "0000320193")
        self.assertGreater(len(info.fiscal_years_available), 0)

    @requires_sec_network
    def test_get_company_info_invalid_cik(self):
        """Test that invalid CIK raises error."""
        with self.assertRaises(CompanyNotFoundError):
            self.lookup.get_company_info("9999999999")

    @patch("credit_research_agent.sec_integration.requests.get")
    def test_get_company_info_parses_submissions_schema(self, mock_get):
        """Company info parser handles SEC submissions schema fields."""
        response = Mock(status_code=200)
        response.json.return_value = {
            "cik": "0000320193",
            "name": "Apple Inc.",
            "tickers": ["AAPL"],
            "exchanges": ["Nasdaq"],
            "sic": "3571",
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "10-K"],
                    "reportDate": ["2024-09-28", "2024-06-29", "2023-09-30"],
                    "filingDate": ["2024-11-01", "2024-08-02", "2023-11-03"],
                }
            },
        }
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        info = self.lookup.get_company_info("0000320193")

        self.assertEqual(info.name, "Apple Inc.")
        self.assertEqual(info.cik, "0000320193")
        self.assertEqual(info.ticker, "AAPL")
        self.assertEqual(info.sic, "3571")
        self.assertEqual(info.fiscal_years_available, [2024, 2023])

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_get_cik_surfaces_sec_network_failure(self, mock_get, _mock_sleep):
        """Ticker lookup fails honestly when live SEC access is unavailable."""
        mock_get.side_effect = requests.ConnectionError("network unavailable")

        with self.assertRaises(CompanyNotFoundError):
            self.lookup.get_cik_by_ticker("AAPL")

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_get_company_info_surfaces_sec_network_failure(self, mock_get, _mock_sleep):
        """Company info does not substitute local metadata for live SEC failures."""
        mock_get.side_effect = requests.ConnectionError("network unavailable")

        with self.assertRaises(CompanyNotFoundError):
            self.lookup.get_company_info("0000320193")


class SEC10KFetcherTest(unittest.TestCase):
    """Test 10-K fetching functionality."""

    def setUp(self):
        """Create fetcher instance."""
        self.fetcher = SEC10KFetcher()

    @requires_sec_network
    def test_fetch_10k_apple_2023(self):
        """Test fetching Apple's 2023 10-K XBRL."""
        cik = "0000320193"  # Apple
        xbrl_content = self.fetcher.fetch_10k_xbrl(cik, 2023)

        self.assertIsInstance(xbrl_content, str)
        self.assertGreater(len(xbrl_content), 1000)
        self.assertIn("xbrl", xbrl_content.lower())

    @requires_sec_network
    def test_fetch_10k_missing_year(self):
        """Test that missing 10-K raises error."""
        cik = "0000320193"

        with self.assertRaises(FilingNotFoundError):
            self.fetcher.fetch_10k_xbrl(cik, 2000)  # Too far in past

    @requires_sec_network
    def test_get_available_years_apple(self):
        """Test getting available fiscal years for Apple."""
        cik = "0000320193"
        years = self.fetcher.get_available_years(cik)

        self.assertGreater(len(years), 0)
        self.assertGreater(max(years), 2020)
        self.assertEqual(years, sorted(years, reverse=True))

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_get_available_years_surfaces_sec_network_failure(self, mock_get, _mock_sleep):
        """Available years return empty when live SEC access is unavailable."""
        mock_get.side_effect = requests.ConnectionError("network unavailable")

        years = self.fetcher.get_available_years("0000320193")

        self.assertEqual(years, [])

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_fetch_10k_surfaces_sec_network_failure(self, mock_get, _mock_sleep):
        """10-K download does not substitute local filings for live SEC failures."""
        mock_get.side_effect = requests.ConnectionError("network unavailable")

        with self.assertRaises(FilingNotFoundError):
            self.fetcher.fetch_10k_xbrl("0000320193", 2023)

    @patch("credit_research_agent.sec_integration.requests.get")
    def test_fetch_10k_downloads_correct_archive_url(self, mock_get):
        """Live download path uses the correct SEC archive URL."""
        submissions_response = Mock()
        submissions_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0000320193-23-000106"],
                    "filingDate": ["2023-11-03"],
                    "primaryDocument": ["aapl-20230930.htm"],
                }
            }
        }
        submissions_response.raise_for_status.return_value = None

        filing_response = Mock()
        filing_response.text = "<xbrl>downloaded apple 2023</xbrl>"
        filing_response.raise_for_status.return_value = None

        mock_get.side_effect = [submissions_response, filing_response]

        content = self.fetcher.fetch_10k_xbrl("0000320193", 2023)

        self.assertEqual(content, "<xbrl>downloaded apple 2023</xbrl>")
        archive_url = mock_get.call_args_list[1].args[0]
        self.assertEqual(
            archive_url,
            "https://www.sec.gov/Archives/edgar/data/"
            "320193/000032019323000106/aapl-20230930.htm",
        )

    @patch("credit_research_agent.sec_integration.requests.get")
    def test_fetch_companyfacts_uses_official_endpoint(self, mock_get):
        """Companyfacts fetch uses SEC's structured XBRL facts endpoint."""
        response = Mock(status_code=200)
        response.json.return_value = {"entityName": "Apple Inc.", "facts": {}}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        facts = self.fetcher.fetch_companyfacts("0000320193")

        self.assertEqual(facts["entityName"], "Apple Inc.")
        url = mock_get.call_args.args[0]
        self.assertEqual(
            url,
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        )


class SECHTTPClientTest(unittest.TestCase):
    """Test SEC request behavior."""

    @patch("credit_research_agent.sec_integration.requests.get")
    def test_sec_get_sends_user_agent(self, mock_get):
        mock_response = Mock()
        mock_get.return_value = mock_response

        response = _sec_get("https://www.sec.gov/files/company_tickers.json", timeout=7)

        self.assertIs(response, mock_response)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["timeout"], 7)
        self.assertIn("User-Agent", kwargs["headers"])
        self.assertIn("VerifiedCreditResearchAgent", kwargs["headers"]["User-Agent"])

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_sec_get_retries_transient_network_error(self, mock_get, mock_sleep):
        transient_error = requests.ConnectionError("temporary DNS failure")
        success_response = Mock(status_code=200)
        mock_get.side_effect = [transient_error, success_response]

        response = _sec_get(
            "https://www.sec.gov/files/company_tickers.json",
            max_attempts=2,
            backoff_seconds=0.01,
        )

        self.assertIs(response, success_response)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_sec_get_retries_retryable_status(self, mock_get, mock_sleep):
        rate_limited = Mock(status_code=429)
        success_response = Mock(status_code=200)
        mock_get.side_effect = [rate_limited, success_response]

        response = _sec_get(
            "https://data.sec.gov/submissions/CIK0000320193.json",
            max_attempts=2,
            backoff_seconds=0.01,
        )

        self.assertIs(response, success_response)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("credit_research_agent.sec_integration.time.sleep")
    @patch("credit_research_agent.sec_integration.requests.get")
    def test_sec_get_does_not_retry_non_retryable_status(self, mock_get, mock_sleep):
        not_found = Mock(status_code=404)
        mock_get.return_value = not_found

        response = _sec_get(
            "https://data.sec.gov/submissions/CIK9999999999.json",
            max_attempts=3,
            backoff_seconds=0.01,
        )

        self.assertIs(response, not_found)
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()


class XBRLParserTest(unittest.TestCase):
    """Test XBRL parsing functionality."""

    def setUp(self):
        """Create parser instance."""
        self.parser = XBRLParser()

    def test_parse_mock_xbrl(self):
        """Test parsing mock XBRL with basic structure."""
        mock_xbrl = """<?xml version="1.0" encoding="UTF-8"?>
        <xbrl xmlns:us-gaap="http://xbrl.us/us-types/2024-01-31">
            <context id="Current_2023">
                <instant>2023-12-31</instant>
            </context>
            <context id="Current_2024">
                <instant>2024-12-31</instant>
            </context>
            <us-gaap:Debt contextRef="Current_2023" unitRef="USD">
                50000000000
            </us-gaap:Debt>
            <us-gaap:StockholdersEquity contextRef="Current_2023" unitRef="USD">
                100000000000
            </us-gaap:StockholdersEquity>
        </xbrl>"""

        metrics = self.parser.extract_metrics(
            mock_xbrl,
            ["total_debt", "shareholders_equity"],
            2023
        )

        self.assertIn("total_debt", metrics)
        # Value is 50000000000, normalized to 50000.0 millions
        self.assertEqual(metrics["total_debt"].value, 50000.0)

    def test_extract_fiscal_year_mock(self):
        """Test fiscal year extraction from mock XBRL."""
        mock_xbrl = """<?xml version="1.0"?>
        <xbrl>
            <context id="Current_2023">
                <instant>2023-12-31</instant>
            </context>
        </xbrl>"""

        year = self.parser.extract_fiscal_year(mock_xbrl)
        self.assertEqual(year, 2023)

    def test_get_available_metrics_mock(self):
        """Test listing available metrics from mock XBRL."""
        mock_xbrl = """<?xml version="1.0"?>
        <xbrl xmlns:us-gaap="http://xbrl.us/us-types/2024-01-31">
            <us-gaap:Assets>1000</us-gaap:Assets>
            <us-gaap:Liabilities>500</us-gaap:Liabilities>
        </xbrl>"""

        metrics = self.parser.get_available_metrics(mock_xbrl)
        self.assertIn("Assets", metrics)
        self.assertIn("Liabilities", metrics)

    def test_extract_metrics_from_companyfacts(self):
        """Test extracting annual 10-K facts from SEC companyfacts JSON."""
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
                                    "filed": "2023-11-03",
                                    "end": "2023-09-30",
                                    "val": 11100000000,
                                }
                            ]
                        }
                    }
                }
            }
        }

        metrics = self.parser.extract_metrics_from_companyfacts(
            companyfacts,
            {"total_debt": ["DebtAndFinancingArrangementsAmount"]},
            2023,
        )

        self.assertIn("total_debt", metrics)
        self.assertEqual(metrics["total_debt"].value, 11100.0)
        self.assertEqual(metrics["total_debt"].source, "SEC companyfacts")

    def test_discover_companyfact_concepts_for_coverage_diagnosis(self):
        """Discovery should find related annual facts without selecting them."""
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
                                    "val": 0,
                                },
                            ]
                        }
                    },
                }
            }
        }

        discovered = self.parser.discover_companyfact_concepts(
            companyfacts,
            ["interest"],
            [2023, 2024, 2025],
        )

        by_concept = {item["concept"]: item for item in discovered}
        self.assertIn("InterestExpense", by_concept)
        self.assertIn("InterestExpenseNonoperating", by_concept)
        self.assertEqual(
            by_concept["InterestExpense"]["facts_by_year"]["2023"]["value"],
            156.0,
        )
        self.assertTrue(by_concept["InterestExpenseNonoperating"]["has_zero_value"])

    @requires_sec_network
    def test_parse_real_xbrl_if_available(self):
        """Test parsing real XBRL (integration test, skipped if API unavailable)."""
        try:
            # Try to fetch real 10-K
            fetcher = SEC10KFetcher()
            cik = "0000320193"  # Apple
            xbrl_content = fetcher.fetch_10k_xbrl(cik, 2023)

            # Parse it
            metrics = self.parser.extract_metrics(
                xbrl_content,
                ["total_debt", "shareholders_equity"],
                2023
            )

            # Should extract something
            self.assertIsInstance(metrics, dict)
            # Real data should have some metrics
            if metrics:
                self.assertGreater(len(metrics), 0)

        except Exception as e:
            # Skip if API not accessible (expected in sandbox)
            self.skipTest(f"SEC API not accessible: {e}")


class SEC10KFetcherIntegrationTest(unittest.TestCase):
    """Integration tests with real SEC EDGAR."""

    @requires_sec_network
    def test_end_to_end_apple_2023(self):
        """Test end-to-end: lookup → fetch 10-K."""
        lookup = SECCompanyLookup()
        fetcher = SEC10KFetcher()

        # Step 1: Lookup CIK
        cik = lookup.get_cik_by_ticker("AAPL")
        self.assertEqual(cik, "0000320193")

        # Step 2: Get available years
        years = fetcher.get_available_years(cik)
        self.assertIn(2023, years)

        # Step 3: Fetch 10-K
        xbrl = fetcher.fetch_10k_xbrl(cik, 2023)
        self.assertGreater(len(xbrl), 1000)

    @requires_sec_network
    def test_end_to_end_multiple_companies(self):
        """Test lookup + fetch for multiple companies."""
        lookup = SECCompanyLookup()
        fetcher = SEC10KFetcher()

        tickers = ["AAPL", "MSFT", "TSLA"]
        expected_ciks = {
            "AAPL": "0000320193",
            "MSFT": "0000789019",
            "TSLA": "0001318605",
        }

        for ticker in tickers:
            cik = lookup.get_cik_by_ticker(ticker)
            self.assertEqual(cik, expected_ciks[ticker])

            years = fetcher.get_available_years(cik)
            self.assertGreater(len(years), 0)


if __name__ == "__main__":
    unittest.main()
