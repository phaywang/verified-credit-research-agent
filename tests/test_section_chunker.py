import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.schemas import FilingDocument, FilingSection
from credit_research_agent.ingestion.section_chunker import chunk_sections


class SectionChunkerTest(unittest.TestCase):
    def test_chunker_preserves_metadata(self):
        document = FilingDocument(
            company="Ford Motor Company",
            ticker="F",
            cik="0000037996",
            fiscal_year=2023,
            filing_type="10-K",
            filing_date="2024-02-07",
            accession_number="0000037996-24-000010",
            source_url="https://www.sec.gov/Archives/example",
            local_path="data/raw/sec/ford/2023/filing.html",
            requested_fiscal_year=2023,
            requested_filing_type="10-K",
        )
        section = FilingSection(
            document=document,
            section_name="Liquidity and Capital Resources",
            section_type="liquidity",
            text=" ".join(["liquidity"] * 30),
        )

        chunks = chunk_sections([section], max_tokens=10, overlap_tokens=2)

        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0].fiscal_year, 2023)
        self.assertEqual(chunks[0].section_name, "Liquidity and Capital Resources")
        self.assertEqual(chunks[0].chunk_id, "F_2023_10K_liquidity_001")
        self.assertEqual(chunks[-1].chunk_id, "F_2023_10K_liquidity_004")


if __name__ == "__main__":
    unittest.main()

