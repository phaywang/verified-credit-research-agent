import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.agent.evidence_checker import (
    check_evidence_coverage,
    is_management_explanation,
)
from credit_research_agent.agent.query_rewriter import rewrite_query
from credit_research_agent.agent.task_parser import parse_task
from credit_research_agent.schemas import Citation, EvidenceChunk


def evidence(chunk_id, year, section_type, text):
    return EvidenceChunk(
        chunk_id=chunk_id,
        fiscal_year=year,
        filing_type="10-K",
        section_name="Liquidity and Capital Resources",
        section_type=section_type,
        reranker_score=0.9,
        rrf_score=0.03,
        evidence_category=[section_type],
        text=text,
        citation=Citation(
            source_url="https://www.sec.gov/Archives/example",
            filing_date="2024-02-07",
            accession_number="0000037996-24-000009",
            chunk_id=chunk_id,
        ),
    )


class EvidenceCheckerTest(unittest.TestCase):
    def test_detects_missing_2025_and_debt(self):
        task = parse_task(
            "How did Ford's debt and liquidity risk change from 2023 to 2025, "
            "and what evidence supports the change?"
        )
        coverage = check_evidence_coverage(
            task,
            [
                evidence(
                    "F_2023_10K_liquidity_001",
                    2023,
                    "liquidity",
                    "Company liquidity was $46.4 billion. We consider liquidity a key metric.",
                )
            ],
            iteration=1,
            max_iterations=3,
        )

        self.assertEqual(coverage.decision, "rewrite_query")
        self.assertIn("2025 evidence", coverage.missing)
        self.assertIn("2023 debt evidence", coverage.missing)
        self.assertIn("2025 debt evidence", coverage.missing)
        self.assertTrue(coverage.has_2023_evidence)
        self.assertFalse(coverage.has_liquidity_evidence)
        self.assertIn("2025 liquidity evidence", coverage.missing)

    def test_query_rewrite_targets_missing_fields(self):
        task = parse_task(
            "How did Ford's debt and liquidity risk change from 2023 to 2025, "
            "and what evidence supports the change?"
        )
        coverage = check_evidence_coverage(task, [], iteration=1, max_iterations=3)
        query = rewrite_query(task, "Ford debt", coverage, iteration=1)

        self.assertIn("2025", query)
        self.assertIn("debt maturities", query)
        self.assertIn("liquidity", query)
        self.assertIn("management discussion", query)

    def test_management_explanation_requires_mda_prose(self):
        table_like = evidence(
            "F_2023_10K_credit_facilities_002",
            2023,
            "credit_facilities",
            "Other unsecured credit facilities $ 1.0 $ 0.8 $ 0.4 reflecting liquidity.",
        )
        mda_prose = evidence(
            "F_2023_10K_mda_027",
            2023,
            "mda",
            (
                "Ford Credit remains well capitalized with a strong balance sheet and "
                "funding diversified across platforms and markets. We expect funding "
                "sources to continue to support liquidity needs."
            ),
        )

        self.assertFalse(is_management_explanation(table_like))
        self.assertTrue(is_management_explanation(mda_prose))


if __name__ == "__main__":
    unittest.main()
