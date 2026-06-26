import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.memory.research_memory import (
    MemoryRunSummary,
    ResearchMemory,
    section_boosts_from_memory,
    select_initial_query,
)


class ResearchMemoryTest(unittest.TestCase):
    def test_update_save_load_and_lookup_topic_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "research_memory.json"
            memory = ResearchMemory(path)
            update = memory.update_from_run(
                MemoryRunSummary(
                    company="Ford Motor Company",
                    ticker="F",
                    risk_theme="debt_liquidity",
                    successful_query="Ford 2023 2025 10-K debt liquidity capital resources debt commitments",
                    failed_queries=["Ford 2023 10-K liquidity cash credit facilities"],
                    useful_sections=[
                        "Liquidity and Capital Resources",
                        "Debt and Commitments",
                        "Committed Credit Facilities",
                    ],
                    verified_metrics=[
                        "company_debt_excluding_ford_credit",
                        "company_liquidity",
                    ],
                    evidence_path="runs/ford_debt_liquidity_2023_2025/evidence_table.json",
                )
            )
            memory.save()

            self.assertEqual(update.successful_queries_added, 1)
            self.assertEqual(update.useful_sections_added, 3)
            self.assertEqual(update.verified_metrics_added, 2)

            loaded = ResearchMemory(path)
            loaded.load()
            topic = loaded.get_topic_memory("Ford Motor Company", "debt_liquidity")

            self.assertIsNotNone(topic)
            self.assertIn("Debt and Commitments", topic.useful_sections)
            self.assertIn("company_liquidity", topic.verified_metrics)
            self.assertIn("runs/ford_debt_liquidity_2023_2025/evidence_table.json", topic.prior_evidence_paths)

    def test_memory_changes_initial_query_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = ResearchMemory(Path(tmpdir) / "research_memory.json")
            memory.update_from_run(
                MemoryRunSummary(
                    company="Ford Motor Company",
                    ticker="F",
                    risk_theme="debt_liquidity",
                    successful_query="Ford 2025 10-K debt commitments liquidity capital resources management discussion",
                    failed_queries=[],
                    useful_sections=[],
                    verified_metrics=[],
                    evidence_path="runs/demo/evidence_table.json",
                )
            )
            topic = memory.get_topic_memory("Ford Motor Company", "debt_liquidity")

            selected = select_initial_query(
                "Ford 2023 10-K liquidity cash credit facilities",
                topic,
                use_memory=True,
            )

            self.assertEqual(
                selected,
                "Ford 2025 10-K debt commitments liquidity capital resources management discussion",
            )

    def test_no_memory_flag_ignores_existing_successful_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = ResearchMemory(Path(tmpdir) / "research_memory.json")
            memory.update_from_run(
                MemoryRunSummary(
                    company="Ford Motor Company",
                    ticker="F",
                    risk_theme="debt_liquidity",
                    successful_query="memory query should be ignored",
                    failed_queries=[],
                    useful_sections=[],
                    verified_metrics=[],
                    evidence_path="runs/demo/evidence_table.json",
                )
            )
            topic = memory.get_topic_memory("Ford Motor Company", "debt_liquidity")

            selected = select_initial_query(
                "Ford 2023 10-K liquidity cash credit facilities",
                topic,
                use_memory=False,
            )

            self.assertEqual(selected, "Ford 2023 10-K liquidity cash credit facilities")

    def test_useful_sections_become_retrieval_boosts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = ResearchMemory(Path(tmpdir) / "research_memory.json")
            memory.update_from_run(
                MemoryRunSummary(
                    company="Ford Motor Company",
                    ticker="F",
                    risk_theme="debt_liquidity",
                    successful_query="Ford debt liquidity",
                    failed_queries=[],
                    useful_sections=[
                        "Liquidity and Capital Resources",
                        "Debt and Commitments",
                    ],
                    verified_metrics=[],
                    evidence_path="runs/demo/evidence_table.json",
                )
            )
            topic = memory.get_topic_memory("Ford Motor Company", "debt_liquidity")

            boosts = section_boosts_from_memory(topic, use_memory=True)

            self.assertGreater(boosts["liquidity"], 1.0)
            self.assertGreater(boosts["debt"], 1.0)
            self.assertEqual(section_boosts_from_memory(topic, use_memory=False), {})


if __name__ == "__main__":
    unittest.main()
