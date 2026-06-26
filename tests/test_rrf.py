import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.retrieval.rrf import reciprocal_rank_fusion
from credit_research_agent.schemas import RetrievalResult


def result(chunk_id, bm25_rank=None, vector_rank=None):
    return RetrievalResult(
        chunk_id=chunk_id,
        query="Ford debt liquidity",
        section_name="Liquidity and Capital Resources",
        fiscal_year=2023,
        bm25_rank=bm25_rank,
        vector_rank=vector_rank,
        text="text",
        source_url="https://www.sec.gov/Archives/example",
    )


class RRFTest(unittest.TestCase):
    def test_rrf_promotes_result_seen_in_both_lists(self):
        fused = reciprocal_rank_fusion(
            [
                [result("a", bm25_rank=1), result("b", bm25_rank=2)],
                [result("b", vector_rank=1), result("c", vector_rank=2)],
            ],
            k=60,
        )

        self.assertEqual(fused[0].chunk_id, "b")
        self.assertEqual(fused[0].bm25_rank, 2)
        self.assertEqual(fused[0].vector_rank, 1)
        self.assertEqual(fused[0].fused_rank, 1)
        self.assertGreater(fused[0].rrf_score, fused[1].rrf_score)


if __name__ == "__main__":
    unittest.main()

