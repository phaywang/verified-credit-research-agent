import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.schemas import EvidenceCoverage, FilingChunk, RetrievalResult


class SchemasTest(unittest.TestCase):
    def test_filing_chunk_serializes_metadata(self):
        chunk = FilingChunk(
            company="Ford Motor Company",
            ticker="F",
            cik="0000037996",
            fiscal_year=2023,
            filing_type="10-K",
            section_name="Liquidity and Capital Resources",
            section_type="liquidity",
            chunk_id="F_2023_10K_liquidity_001",
            text="Ford discussed liquidity and capital resources.",
            source_url="https://www.sec.gov/Archives/example",
            filing_date="2024-02-07",
            accession_number="0000037996-24-000010",
            char_start=100,
            char_end=200,
        )

        data = chunk.to_jsonable()
        self.assertEqual(data["ticker"], "F")
        self.assertEqual(data["fiscal_year"], 2023)
        self.assertEqual(data["section_type"], "liquidity")

    def test_retrieval_result_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            RetrievalResult(
                chunk_id="F_2023_10K_liquidity_001",
                query="Ford liquidity",
                section_name="Liquidity and Capital Resources",
                fiscal_year=2023,
                text="...",
                source_url="https://www.sec.gov/Archives/example",
                unexpected=True,
            )

    def test_evidence_coverage_defaults_to_rewrite(self):
        coverage = EvidenceCoverage()

        self.assertEqual(coverage.decision, "rewrite_query")
        self.assertEqual(coverage.missing, [])
        self.assertFalse(coverage.has_2023_evidence)


if __name__ == "__main__":
    unittest.main()

