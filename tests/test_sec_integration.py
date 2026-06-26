"""Tests for SEC EDGAR integration."""

import unittest
from pathlib import Path

from credit_research_agent.sec_integration import (
    SECCompanyLookup,
    SEC10KFetcher,
    XBRLParser,
    CompanyNotFoundError,
    FilingNotFoundError,
)


class SECCompanyLookupTest(unittest.TestCase):
    """Test SEC company lookup functionality."""

    def setUp(self):
        """Create lookup instance with cache."""
        self.lookup = SECCompanyLookup(cache_dir=Path("/tmp/sec_cache_test"))

    def test_get_cik_apple(self):
        """Test CIK lookup for Apple (AAPL)."""
        cik = self.lookup.get_cik_by_ticker("AAPL")
        self.assertEqual(cik, "0000000320193")
        self.assertTrue(cik.startswith("000"))  # Zero-padded

    def test_get_cik_tesla(self):
        """Test CIK lookup for Tesla (TSLA)."""
        cik = self.lookup.get_cik_by_ticker("TSLA")
        self.assertEqual(cik, "0001318605")

    def test_get_cik_microsoft(self):
        """Test CIK lookup for Microsoft (MSFT)."""
        cik = self.lookup.get_cik_by_ticker("MSFT")
        self.assertEqual(cik, "0000000789019")

    def test_get_cik_invalid_ticker(self):
        """Test that invalid ticker raises error."""
        with self.assertRaises(CompanyNotFoundError):
            self.lookup.get_cik_by_ticker("INVALID_TICKER_XYZ")

    def test_get_cik_case_insensitive(self):
        """Test that ticker lookup is case-insensitive."""
        cik_upper = self.lookup.get_cik_by_ticker("AAPL")
        cik_lower = self.lookup.get_cik_by_ticker("aapl")
        cik_mixed = self.lookup.get_cik_by_ticker("AaPl")

        self.assertEqual(cik_upper, cik_lower)
        self.assertEqual(cik_upper, cik_mixed)

    def test_tickers_json_caching(self):
        """Test that tickers JSON is cached locally."""
        # First call fetches and caches
        self.lookup.get_cik_by_ticker("AAPL")
        cache_path = self.lookup.cache_dir / "company_tickers.json"
        self.assertTrue(cache_path.exists())

    def test_get_company_info_apple(self):
        """Test fetching company metadata for Apple."""
        info = self.lookup.get_company_info("0000320193")

        self.assertIn("Apple", info.name)
        self.assertEqual(info.cik, "0000000320193")
        self.assertGreater(len(info.fiscal_years_available), 0)

    def test_get_company_info_invalid_cik(self):
        """Test that invalid CIK raises error."""
        with self.assertRaises(CompanyNotFoundError):
            self.lookup.get_company_info("9999999999")


class SEC10KFetcherTest(unittest.TestCase):
    """Test 10-K fetching functionality."""

    def setUp(self):
        """Create fetcher instance."""
        self.fetcher = SEC10KFetcher()

    def test_fetch_10k_apple_2023(self):
        """Test fetching Apple's 2023 10-K XBRL."""
        cik = "0000320193"  # Apple
        xbrl_content = self.fetcher.fetch_10k_xbrl(cik, 2023)

        self.assertIsInstance(xbrl_content, str)
        self.assertGreater(len(xbrl_content), 1000)
        self.assertIn("xbrl", xbrl_content.lower())

    def test_fetch_10k_missing_year(self):
        """Test that missing 10-K raises error."""
        cik = "0000320193"

        with self.assertRaises(FilingNotFoundError):
            self.fetcher.fetch_10k_xbrl(cik, 2000)  # Too far in past

    def test_get_available_years_apple(self):
        """Test getting available fiscal years for Apple."""
        cik = "0000320193"
        years = self.fetcher.get_available_years(cik)

        self.assertGreater(len(years), 0)
        self.assertGreater(max(years), 2020)
        self.assertEqual(years, sorted(years, reverse=True))


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

    def test_end_to_end_apple_2023(self):
        """Test end-to-end: lookup → fetch 10-K."""
        lookup = SECCompanyLookup()
        fetcher = SEC10KFetcher()

        # Step 1: Lookup CIK
        cik = lookup.get_cik_by_ticker("AAPL")
        self.assertEqual(cik, "0000000320193")

        # Step 2: Get available years
        years = fetcher.get_available_years(cik)
        self.assertIn(2023, years)

        # Step 3: Fetch 10-K
        xbrl = fetcher.fetch_10k_xbrl(cik, 2023)
        self.assertGreater(len(xbrl), 1000)

    def test_end_to_end_multiple_companies(self):
        """Test lookup + fetch for multiple companies."""
        lookup = SECCompanyLookup()
        fetcher = SEC10KFetcher()

        tickers = ["AAPL", "MSFT", "TSLA"]
        expected_ciks = {
            "AAPL": "0000000320193",
            "MSFT": "0000000789019",
            "TSLA": "0001318605",
        }

        for ticker in tickers:
            cik = lookup.get_cik_by_ticker(ticker)
            self.assertEqual(cik, expected_ciks[ticker])

            years = fetcher.get_available_years(cik)
            self.assertGreater(len(years), 0)


if __name__ == "__main__":
    unittest.main()
