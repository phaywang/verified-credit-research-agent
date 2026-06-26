import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.agent.evidence_checker import check_evidence_coverage
from credit_research_agent.agent.task_parser import parse_task
from credit_research_agent.schemas import Citation, EvidenceChunk
from credit_research_agent.skills.skill_loader import load_debt_liquidity_skill


def write_skill(path: Path, required_categories: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Debt and Liquidity Research Skill",
                "",
                "required_evidence_categories:",
                *[f"- {category}" for category in required_categories],
                "",
                "required_sections:",
                "- Liquidity and Capital Resources",
                "- Debt and Commitments",
                "- Management's Discussion and Analysis",
                "",
                "rules:",
                "- verified_numeric_changes_must_appear_in_conclusions: true",
                "- unsupported_numeric_claims_must_be_excluded: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def evidence(chunk_id: str, year: int, section_type: str, text: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id,
        fiscal_year=year,
        filing_type="10-K",
        section_name=section_type,
        section_type=section_type,
        reranker_score=0.9,
        rrf_score=0.03,
        evidence_category=[section_type],
        text=text,
        citation=Citation(
            source_url="https://www.sec.gov/Archives/example",
            filing_date="2026-02-11",
            accession_number="0000037996-26-000015",
            chunk_id=chunk_id,
        ),
    )


class SkillLoaderTest(unittest.TestCase):
    def test_loads_required_categories_and_verified_conclusion_rule(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = Path(tmpdir) / "skills" / "debt_liquidity_research" / "SKILL.md"
            write_skill(
                skill_path,
                ["debt", "liquidity", "management_explanation", "numeric_facts"],
            )

            skill = load_debt_liquidity_skill(skill_path)

            self.assertEqual(skill.name, "Debt and Liquidity Research Skill")
            self.assertEqual(
                skill.required_evidence_categories,
                ["debt", "liquidity", "management_explanation", "numeric_facts"],
            )
            self.assertTrue(skill.require_verified_numeric_conclusions)
            self.assertIn("Debt and Commitments", skill.required_sections)

    def test_skill_required_category_changes_evidence_checker_behavior(self):
        task = parse_task(
            "How did Ford's debt and liquidity risk change from 2023 to 2025, "
            "and what evidence supports the change?"
        )
        evidence_chunks = [
            evidence("F_2023_10K_debt_001", 2023, "debt", "Company debt excluding Ford Credit was $19.9 billion."),
            evidence("F_2025_10K_debt_001", 2025, "debt", "Company debt excluding Ford Credit was $21.9 billion."),
            evidence("F_2023_10K_liquidity_001", 2023, "liquidity", "Company liquidity was $46.4 billion."),
            evidence("F_2025_10K_liquidity_001", 2025, "liquidity", "Company liquidity was $49.8 billion."),
            evidence(
                "F_2023_10K_mda_001",
                2023,
                "mda",
                "Ford Credit remains well capitalized with diversified funding. We expect funding sources to support liquidity needs.",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = Path(tmpdir) / "SKILL.md"
            write_skill(
                skill_path,
                ["debt", "liquidity", "management_explanation", "numeric_facts"],
            )
            baseline_skill = load_debt_liquidity_skill(skill_path)
            baseline = check_evidence_coverage(
                task,
                evidence_chunks,
                iteration=1,
                max_iterations=3,
                skill=baseline_skill,
            )
            self.assertNotIn("risk_factors", baseline.missing)

            write_skill(
                skill_path,
                ["debt", "liquidity", "management_explanation", "numeric_facts", "risk_factors"],
            )
            stricter_skill = load_debt_liquidity_skill(skill_path)
            stricter = check_evidence_coverage(
                task,
                evidence_chunks,
                iteration=1,
                max_iterations=3,
                skill=stricter_skill,
            )

            self.assertEqual(stricter.decision, "rewrite_query")
            self.assertIn("risk_factors evidence", stricter.missing)


if __name__ == "__main__":
    unittest.main()
