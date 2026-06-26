import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.retrieval.bm25_index import BM25Index
from credit_research_agent.schemas import FilingChunk


def make_chunk(chunk_id, text, section_type="liquidity"):
    return FilingChunk(
        company="Ford Motor Company",
        ticker="F",
        cik="0000037996",
        fiscal_year=2023,
        filing_type="10-K",
        section_name="Liquidity and Capital Resources",
        section_type=section_type,
        chunk_id=chunk_id,
        text=text,
        source_url="https://www.sec.gov/Archives/example",
        filing_date="2024-02-07",
        accession_number="0000037996-24-000009",
    )


class BM25IndexTest(unittest.TestCase):
    def test_search_returns_lexical_match_first(self):
        chunks = [
            make_chunk("a", "cash liquidity credit facilities"),
            make_chunk("b", "vehicle production warranty"),
        ]
        index = BM25Index()
        index.build(chunks)

        results = index.search("liquidity credit", top_n=2)

        self.assertEqual(results[0].chunk_id, "a")
        self.assertEqual(results[0].bm25_rank, 1)
        self.assertGreater(results[0].bm25_score, 0)


if __name__ == "__main__":
    unittest.main()

