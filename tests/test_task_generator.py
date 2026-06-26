"""Tests for multi-company task generator."""

import unittest

from credit_research_agent.task_generator import (
    TaskGenerator, get_generator, reset_generator
)


class TaskGeneratorTest(unittest.TestCase):
    """Test dynamic task generation from configuration."""

    def setUp(self):
        """Reset generator before each test."""
        reset_generator()

    def test_generate_task_ford_debt_liquidity(self):
        """Test generating Ford debt/liquidity task."""
        gen = get_generator()
        task = gen.generate_task("ford", "debt_liquidity")

        self.assertEqual(task.company_id, "ford")
        self.assertEqual(task.risk_theme_id, "debt_liquidity")
        self.assertEqual(len(task.comparison_years), 2)
        self.assertIn("debt", task.question.lower())
        self.assertIn("ford", task.question.lower())
        self.assertIn("2023", task.question)
        self.assertIn("2025", task.question)

    def test_generate_task_apple_leverage(self):
        """Test generating Apple leverage analysis task."""
        gen = get_generator()
        task = gen.generate_task("apple", "leverage_analysis")

        self.assertEqual(task.company_id, "apple")
        self.assertEqual(task.risk_theme_id, "leverage_analysis")
        self.assertIn("Apple", task.question)
        self.assertIn("leverage", task.question.lower())

    def test_generate_task_microsoft_solvency(self):
        """Test generating Microsoft solvency assessment task."""
        gen = get_generator()
        task = gen.generate_task("microsoft", "solvency_assessment")

        self.assertEqual(task.company_id, "microsoft")
        self.assertEqual(task.risk_theme_id, "solvency_assessment")
        self.assertIn("Microsoft", task.question)
        self.assertIn("solvency", task.question.lower())

    def test_generate_task_with_explicit_years(self):
        """Test task generation with explicit comparison years."""
        gen = get_generator()
        task = gen.generate_task("ford", "debt_liquidity", [2023, 2025])

        self.assertEqual(task.comparison_years, [2023, 2025])
        self.assertIn("2023", task.question)
        self.assertIn("2025", task.question)

    def test_generate_task_spec_ford(self):
        """Test generating TaskSpec for M3 agent (Ford)."""
        gen = get_generator()
        spec = gen.generate_task_spec("ford", "debt_liquidity")

        self.assertEqual(spec.ticker, "F")
        self.assertEqual(spec.company, "Ford Motor Company")
        self.assertEqual(spec.risk_theme, "debt_liquidity")
        self.assertIn("debt", spec.question.lower())
        self.assertEqual(len(spec.required_evidence), 4)  # debt, liquidity, mgt, numeric

    def test_generate_task_spec_apple(self):
        """Test generating TaskSpec for Apple leverage."""
        gen = get_generator()
        spec = gen.generate_task_spec("apple", "leverage_analysis")

        self.assertEqual(spec.ticker, "AAPL")
        self.assertEqual(spec.company, "Apple Inc.")
        self.assertEqual(spec.risk_theme, "leverage_analysis")

    def test_generate_task_spec_microsoft(self):
        """Test generating TaskSpec for Microsoft solvency."""
        gen = get_generator()
        spec = gen.generate_task_spec("microsoft", "solvency_assessment")

        self.assertEqual(spec.ticker, "MSFT")
        self.assertEqual(spec.company, "Microsoft Corporation")
        self.assertEqual(spec.risk_theme, "solvency_assessment")

    def test_task_has_evidence_requirements(self):
        """Test that task includes evidence requirements from theme."""
        gen = get_generator()
        task = gen.generate_task("ford", "leverage_analysis")

        # Leverage theme requires debt, equity, interest expense
        self.assertIn("debt", task.evidence_requirements)
        self.assertIn("equity", task.evidence_requirements)
        self.assertIn("interest_expense", task.evidence_requirements)

    def test_task_has_required_sections(self):
        """Test that task includes required sections from theme."""
        gen = get_generator()
        task = gen.generate_task("apple", "solvency_assessment")

        # Should include Balance Sheet and Cash Flows
        self.assertTrue(
            any("Balance Sheet" in section for section in task.required_sections)
        )
        self.assertTrue(
            any("Cash Flows" in section for section in task.required_sections)
        )

    def test_generator_singleton(self):
        """Test that get_generator returns singleton."""
        reset_generator()
        gen1 = get_generator()
        gen2 = get_generator()
        self.assertIs(gen1, gen2)

    def test_all_company_theme_combinations(self):
        """Test that generator works for all (company, theme) combos."""
        gen = get_generator()
        companies = ["ford", "apple", "microsoft"]
        themes = ["debt_liquidity", "leverage_analysis", "solvency_assessment"]

        for company in companies:
            for theme in themes:
                task = gen.generate_task(company, theme)
                self.assertEqual(task.company_id, company)
                self.assertEqual(task.risk_theme_id, theme)
                self.assertIn(company, task.question.lower())
                self.assertGreater(len(task.required_sections), 0)


if __name__ == "__main__":
    unittest.main()
