import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.retrieval.vector_index import VectorIndex
from credit_research_agent.schemas import FilingChunk


def make_chunk(chunk_id):
    return FilingChunk(
        company="Ford Motor Company",
        ticker="F",
        cik="0000037996",
        fiscal_year=2023,
        filing_type="10-K",
        section_name="Debt",
        section_type="debt",
        chunk_id=chunk_id,
        text="text",
        source_url="https://www.sec.gov/Archives/example",
        filing_date="2024-02-07",
        accession_number="0000037996-24-000009",
    )


class VectorIndexTest(unittest.TestCase):
    def test_numpy_cosine_search(self):
        index = VectorIndex()
        index.build(
            [make_chunk("a"), make_chunk("b")],
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        )

        results = index.search(
            "query",
            np.array([0.9, 0.1], dtype=np.float32),
            top_n=2,
        )

        self.assertEqual(results[0].chunk_id, "a")
        self.assertEqual(results[0].vector_rank, 1)
        self.assertGreater(results[0].vector_score, results[1].vector_score)


if __name__ == "__main__":
    unittest.main()

