"""Tests for multi-company configuration loader."""

import unittest
from pathlib import Path

from credit_research_agent.config_loader import (
    ConfigLoader, CompanyConfig, RiskThemeConfig, MetricDefinition,
    get_loader, reset_loader
)


class ConfigLoaderTest(unittest.TestCase):
    """Test configuration loading from YAML files."""

    def setUp(self):
        """Reset loader before each test."""
        reset_loader()

    def test_load_companies(self):
        """Test loading company configurations."""
        loader = get_loader()
        companies = loader.load_companies()

        # Verify Ford is present
        self.assertIn("ford", companies)
        ford = companies["ford"]
        self.assertEqual(ford.ticker, "F")
        self.assertEqual(ford.name, "Ford Motor Company")
        self.assertIn(2023, ford.fiscal_years)
        self.assertIn(2025, ford.fiscal_years)

    def test_load_companies_caches(self):
        """Test that companies are cached (same instance returned)."""
        loader = get_loader()
        companies1 = loader.load_companies()
        companies2 = loader.load_companies()
        self.assertIs(companies1, companies2)

    def test_get_company_by_id(self):
        """Test retrieving a specific company."""
        loader = get_loader()
        ford = loader.get_company("ford")
        self.assertEqual(ford.ticker, "F")

    def test_get_company_raises_on_unknown(self):
        """Test that unknown company raises KeyError."""
        loader = get_loader()
        with self.assertRaises(KeyError):
            loader.get_company("unknown_company")

    def test_load_risk_themes(self):
        """Test loading risk theme configurations."""
        loader = get_loader()
        themes = loader.load_risk_themes()

        # Verify debt_liquidity theme
        self.assertIn("debt_liquidity", themes)
        theme = themes["debt_liquidity"]
        self.assertIn("debt", theme.required_evidence_categories)
        self.assertIn("liquidity", theme.required_evidence_categories)
        self.assertIn("total_debt", theme.key_metrics)

    def test_load_risk_themes_has_new_themes(self):
        """Test that new risk themes are present."""
        loader = get_loader()
        themes = loader.load_risk_themes()

        # Verify new themes exist
        self.assertIn("leverage_analysis", themes)
        self.assertIn("solvency_assessment", themes)

        # Verify leverage theme has correct metrics
        leverage = themes["leverage_analysis"]
        self.assertIn("total_debt", leverage.key_metrics)
        self.assertIn("shareholders_equity", leverage.key_metrics)
        self.assertIn("interest_expense", leverage.key_metrics)

    def test_load_metrics(self):
        """Test loading metric definitions."""
        loader = get_loader()
        metrics = loader.load_metrics()

        # Verify key metrics exist
        self.assertIn("total_debt", metrics)
        self.assertIn("cash_and_equivalents", metrics)
        self.assertIn("shareholders_equity", metrics)

        # Verify metric details
        total_debt = metrics["total_debt"]
        self.assertEqual(total_debt.unit, "USD")
        self.assertGreater(len(total_debt.xbrl_selectors), 0)
        self.assertGreater(len(total_debt.text_patterns), 0)

    def test_get_metric_by_name(self):
        """Test retrieving a specific metric."""
        loader = get_loader()
        metric = loader.get_metric("total_debt")
        self.assertEqual(metric.name, "total_debt")
        self.assertIn("debt", metric.description.lower())

    def test_get_metric_raises_on_unknown(self):
        """Test that unknown metric raises KeyError."""
        loader = get_loader()
        with self.assertRaises(KeyError):
            loader.get_metric("unknown_metric")

    def test_load_skill_debt_liquidity(self):
        """Test loading debt_liquidity skill."""
        loader = get_loader()
        skill = loader.load_skill("debt_liquidity_research")

        self.assertIn("Debt and Liquidity", skill)
        self.assertIn("Required Evidence", skill)
        self.assertIn("research steps", skill.lower())

    def test_load_skill_leverage_analysis(self):
        """Test loading leverage_analysis skill."""
        loader = get_loader()
        skill = loader.load_skill("leverage_analysis")

        self.assertIn("Leverage Analysis", skill)
        self.assertIn("Debt-to-Equity", skill)

    def test_load_skill_raises_on_unknown(self):
        """Test that unknown skill raises FileNotFoundError."""
        loader = get_loader()
        with self.assertRaises(FileNotFoundError):
            loader.load_skill("unknown_skill")

    def test_global_loader_singleton(self):
        """Test that get_loader returns singleton."""
        reset_loader()
        loader1 = get_loader()
        loader2 = get_loader()
        self.assertIs(loader1, loader2)

    def test_configuration_supports_multi_company(self):
        """Test that configuration supports multiple companies."""
        loader = get_loader()
        companies = loader.load_companies()

        # Verify we have at least 3 companies for expansion
        self.assertGreaterEqual(len(companies), 3)
        self.assertIn("ford", companies)
        self.assertIn("apple", companies)
        self.assertIn("microsoft", companies)

    def test_configuration_supports_multi_theme(self):
        """Test that configuration supports multiple risk themes."""
        loader = get_loader()
        themes = loader.load_risk_themes()

        # Verify we have at least 3 themes for expansion
        self.assertGreaterEqual(len(themes), 3)
        self.assertIn("debt_liquidity", themes)
        self.assertIn("leverage_analysis", themes)
        self.assertIn("solvency_assessment", themes)

    def test_apple_configuration_valid(self):
        """Test that Apple configuration is complete."""
        loader = get_loader()
        apple = loader.get_company("apple")

        self.assertEqual(apple.ticker, "AAPL")
        self.assertEqual(apple.name, "Apple Inc.")
        self.assertGreaterEqual(len(apple.fiscal_years), 2)
        self.assertIn("10-K", apple.filing_types)

    def test_microsoft_configuration_valid(self):
        """Test that Microsoft configuration is complete."""
        loader = get_loader()
        microsoft = loader.get_company("microsoft")

        self.assertEqual(microsoft.ticker, "MSFT")
        self.assertEqual(microsoft.name, "Microsoft Corporation")
        self.assertGreaterEqual(len(microsoft.fiscal_years), 2)

    def test_leverage_theme_has_required_metrics(self):
        """Test that leverage_analysis theme has all required metrics."""
        loader = get_loader()
        theme = loader.get_risk_theme("leverage_analysis")

        required = {"total_debt", "shareholders_equity", "interest_expense"}
        self.assertTrue(required.issubset(set(theme.key_metrics)))

    def test_solvency_theme_has_required_metrics(self):
        """Test that solvency_assessment theme has all required metrics."""
        loader = get_loader()
        theme = loader.get_risk_theme("solvency_assessment")

        required = {"current_assets", "current_liabilities", "operating_cash_flow"}
        self.assertTrue(required.issubset(set(theme.key_metrics)))


if __name__ == "__main__":
    unittest.main()
