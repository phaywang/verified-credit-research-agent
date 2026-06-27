"""Tests for SEC statement table extraction."""

import unittest

from credit_research_agent.sec_integration import FilingPackage
from credit_research_agent.statement_extractor import StatementTableExtractor


class StatementTableExtractorTest(unittest.TestCase):
    """Test extracting statement rows from SEC-style HTML tables."""

    def test_extracts_cash_flow_capex_with_inline_concept(self):
        html = """
        <html><body>
          <table>
            <tr><th>Year Ended</th><th>Jan 31, 2025</th><th>Jan 31, 2024</th></tr>
            <tr><td>Cash flows from operating activities:</td><td></td><td></td></tr>
            <tr><td>Net cash provided by operating activities</td>
              <td><ix:nonFraction name="us-gaap:NetCashProvidedByUsedInOperatingActivities"
                  contextRef="c1" unitRef="usd" scale="6">1,000</ix:nonFraction></td>
              <td>900</td></tr>
            <tr><td>Cash flows from investing activities:</td><td></td><td></td></tr>
            <tr><td>Purchases of property and equipment</td>
              <td><ix:nonFraction name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"
                  contextRef="c1" unitRef="usd" scale="6">(250)</ix:nonFraction></td>
              <td>(200)</td></tr>
            <tr><td>Cash flows from financing activities:</td><td></td><td></td></tr>
            <tr><td>Dividends paid</td><td>(50)</td><td>(40)</td></tr>
          </table>
        </body></html>
        """
        package = FilingPackage(
            company="Example Co",
            ticker="EX",
            cik="0000000000",
            fiscal_year=2025,
            filing_date="2026-02-01",
            report_date="2025-01-31",
            accession_number="0000000000-26-000001",
            primary_doc_url="https://www.sec.gov/example.htm",
            html=html,
        )

        rows = StatementTableExtractor().extract(package)
        capex = [
            row for row in rows
            if row.normalized_label == "purchases of property and equipment"
            and row.fiscal_year == 2025
        ][0]

        self.assertEqual(capex.statement_type, "cash_flow_statement")
        self.assertEqual(capex.value, -250.0)
        self.assertEqual(capex.xbrl_concept, "PaymentsToAcquirePropertyPlantAndEquipment")
        self.assertEqual(capex.confidence, "high")


if __name__ == "__main__":
    unittest.main()
