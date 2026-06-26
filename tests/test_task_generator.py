"""Tests for multi-company task generator."""

import unittest
from unittest.mock import MagicMock, patch

from credit_research_agent.task_generator import (
    TaskGenerator, get_generator, reset_generator
)
from credit_research_agent.sec_integration import CompanyInfo, CompanyNotFoundError


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


class UniversalTaskGeneratorTest(unittest.TestCase):
    """Test universal (ticker-based) task generation."""

    def setUp(self):
        """Reset generator before each test."""
        reset_generator()

    def test_find_preconfigured_company_by_ticker(self):
        """Test finding pre-configured company by ticker."""
        gen = TaskGenerator()

        # These are pre-configured
        company_id = gen._find_company_id_by_ticker("AAPL")
        self.assertEqual(company_id, "apple")

        company_id = gen._find_company_id_by_ticker("F")
        self.assertEqual(company_id, "ford")

    def test_find_company_not_in_config(self):
        """Test that unknown tickers raise ValueError."""
        gen = TaskGenerator()

        with self.assertRaises(ValueError):
            gen._find_company_id_by_ticker("UNKNOWN_TICKER_XYZ")

    def test_generate_task_spec_universal_preconfigured(self):
        """Test universal task generation for pre-configured company."""
        gen = TaskGenerator()

        # Apple is pre-configured
        spec = gen.generate_task_spec_universal("AAPL", "leverage_analysis")

        self.assertEqual(spec.ticker, "AAPL")
        self.assertEqual(spec.company, "Apple Inc.")
        self.assertEqual(spec.risk_theme, "leverage_analysis")
        self.assertIn("Apple", spec.question)

    def test_generate_task_spec_universal_case_insensitive(self):
        """Test that universal generation is case-insensitive."""
        gen = TaskGenerator()

        spec1 = gen.generate_task_spec_universal("AAPL", "leverage_analysis")
        spec2 = gen.generate_task_spec_universal("aapl", "leverage_analysis")

        self.assertEqual(spec1.ticker, spec2.ticker)
        self.assertEqual(spec1.company, spec2.company)

    @patch("credit_research_agent.task_generator.SECCompanyLookup")
    def test_generate_task_spec_universal_new_ticker(self, mock_lookup_class):
        """Test universal task generation for new ticker (SEC lookup)."""
        mock_lookup = MagicMock()
        mock_lookup_class.return_value = mock_lookup

        # Use a company not in pre-configured list (NVDA = Nvidia)
        mock_company = CompanyInfo(
            name="NVIDIA Corporation",
            cik="0001318605",
            ticker="NVDA",
            sic="3674",
            sector="Semiconductors",
            fiscal_years_available=[2023, 2024],
        )

        mock_lookup.get_cik_by_ticker.return_value = "0001318605"
        mock_lookup.get_company_info.return_value = mock_company

        gen = TaskGenerator()
        spec = gen.generate_task_spec_universal("NVDA", "leverage_analysis")

        self.assertEqual(spec.ticker, "NVDA")
        self.assertEqual(spec.company, "NVIDIA Corporation")
        self.assertEqual(spec.cik, "0001318605")
        self.assertEqual(spec.risk_theme, "leverage_analysis")

    @patch("credit_research_agent.task_generator.SECCompanyLookup")
    def test_generate_task_spec_universal_invalid_ticker(self, mock_lookup_class):
        """Test universal task generation with invalid ticker."""
        mock_lookup = MagicMock()
        mock_lookup_class.return_value = mock_lookup

        mock_lookup.get_cik_by_ticker.side_effect = CompanyNotFoundError(
            "Ticker not found"
        )

        gen = TaskGenerator()

        with self.assertRaises(CompanyNotFoundError):
            gen.generate_task_spec_universal("INVALID_XYZ", "leverage_analysis")

    def test_generate_task_spec_universal_with_years(self):
        """Test universal generation with explicit years."""
        gen = TaskGenerator()

        spec = gen.generate_task_spec_universal(
            "AAPL", "leverage_analysis", [2022, 2023, 2024]
        )

        self.assertEqual(spec.years, [2022, 2023, 2024])

    @patch("credit_research_agent.task_generator.SECCompanyLookup")
    def test_generate_task_spec_universal_defaults_to_recent_years(
        self, mock_lookup_class
    ):
        """Test that universal generation defaults to recent fiscal years."""
        mock_lookup = MagicMock()
        mock_lookup_class.return_value = mock_lookup

        # Use a company not in pre-configured list (JPM = JPMorgan Chase)
        mock_company = CompanyInfo(
            name="JPMorgan Chase & Co.",
            cik="0000047709",
            ticker="JPM",
            sic="6021",
            sector="Finance",
            fiscal_years_available=[2020, 2021, 2022, 2023, 2024],
        )

        mock_lookup.get_cik_by_ticker.return_value = "0000047709"
        mock_lookup.get_company_info.return_value = mock_company

        gen = TaskGenerator()
        spec = gen.generate_task_spec_universal("JPM", "leverage_analysis")

        # Should default to last 2 years
        self.assertEqual(spec.years, [2023, 2024])


if __name__ == "__main__":
    unittest.main()
