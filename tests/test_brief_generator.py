"""Tests for generic brief generator."""

import unittest

from credit_research_agent.brief_generator import (
    BriefGenerator, MetricResult, VerifiedMetricsSet
)


class BriefGeneratorTest(unittest.TestCase):
    """Test brief generation from verified metrics."""

    def setUp(self):
        """Create sample metrics for testing."""
        self.ford_metrics = VerifiedMetricsSet(
            company_name="Ford Motor Company",
            fiscal_years=[2023, 2025],
            metrics={
                2023: [
                    MetricResult(
                        metric_name="total_debt",
                        fiscal_year=2023,
                        value=19.944,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                    MetricResult(
                        metric_name="cash_equivalents",
                        fiscal_year=2023,
                        value=10.5,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                ],
                2025: [
                    MetricResult(
                        metric_name="total_debt",
                        fiscal_year=2025,
                        value=21.9,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                    MetricResult(
                        metric_name="cash_equivalents",
                        fiscal_year=2025,
                        value=9.8,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                ],
            },
        )

        self.leverage_metrics = VerifiedMetricsSet(
            company_name="Apple Inc.",
            fiscal_years=[2023, 2024],
            metrics={
                2023: [
                    MetricResult(
                        metric_name="total_debt",
                        fiscal_year=2023,
                        value=106.9,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                    MetricResult(
                        metric_name="shareholders_equity",
                        fiscal_year=2023,
                        value=63.1,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                ],
                2024: [
                    MetricResult(
                        metric_name="total_debt",
                        fiscal_year=2024,
                        value=110.5,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                    MetricResult(
                        metric_name="shareholders_equity",
                        fiscal_year=2024,
                        value=70.6,
                        unit="USD billions",
                        status="verified",
                        source="XBRL",
                    ),
                ],
            },
        )

    def test_generate_brief_debt_liquidity(self):
        """Test brief generation for debt/liquidity theme."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        # Check structure
        self.assertIn("# Ford Motor Company", brief)
        self.assertIn("## Executive Summary", brief)
        self.assertIn("## Key Metrics", brief)
        self.assertIn("## Conclusion", brief)

        # Check content
        self.assertIn("2023", brief)
        self.assertIn("2025", brief)
        self.assertIn("verified", brief)

    def test_generate_brief_leverage(self):
        """Test brief generation for leverage theme."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Apple Inc.",
            "leverage_analysis",
            self.leverage_metrics,
        )

        self.assertIn("# Apple Inc.", brief)
        self.assertIn("leverage", brief.lower())
        self.assertIn("debt", brief.lower())
        self.assertIn("equity", brief.lower())

    def test_metrics_table_generation(self):
        """Test that metrics are formatted as a table."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        # Check for table structure
        self.assertIn("| Metric |", brief)
        self.assertIn("| Value |", brief)
        self.assertIn("| Status |", brief)
        self.assertIn("✓", brief)  # verified icon

    def test_brief_has_execution_summary(self):
        """Test that brief includes executive summary."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        self.assertIn("Executive Summary", brief)
        # Should mention year comparison
        self.assertIn("2023", brief)
        self.assertIn("2025", brief)

    def test_brief_has_conclusion(self):
        """Test that brief includes a conclusion."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        self.assertIn("## Conclusion", brief)
        self.assertIn("verified", brief.lower())

    def test_brief_includes_verified_changes(self):
        """Test that brief includes deterministic metric changes."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        self.assertIn("## Verified Changes", brief)
        self.assertIn("| total_debt | 19.94 USD billions | 21.90 USD billions | +1.96 USD billions | +9.81% | increased |", brief)
        self.assertIn("| cash_equivalents | 10.50 USD billions | 9.80 USD billions | -0.70 USD billions | -6.67% | decreased |", brief)
        self.assertIn("Analyst notes", brief)
        self.assertIn("higher leverage", brief)

    def test_brief_includes_credit_work_product_sections(self):
        """Test that brief reads like an analyst work product, not only metrics."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        self.assertIn("## Credit Read-Through", brief)
        self.assertIn("## Watch Items for Analyst Review", brief)
        self.assertIn("## Verification Basis", brief)
        self.assertIn("## Limitations", brief)
        self.assertIn("## Follow-Up Questions", brief)
        self.assertIn("Source", brief)
        self.assertIn("Verified in both years", brief)

    def test_brief_withholds_change_when_metric_not_verified_in_both_years(self):
        """Test that trend conclusions require verified values in both years."""
        metrics = VerifiedMetricsSet(
            company_name="Test Corp",
            fiscal_years=[2023, 2024],
            metrics={
                2023: [
                    MetricResult("debt", 2023, 100.0, "USD M", "verified", "XBRL"),
                ],
                2024: [
                    MetricResult("cash", 2024, 50.0, "USD M", "verified", "XBRL"),
                ],
            },
        )

        gen = BriefGenerator()
        brief = gen.generate_brief("Test Corp", "debt_liquidity", metrics)

        self.assertIn("No metrics have verified values in both 2023 and 2024", brief)

    def test_brief_markdown_format(self):
        """Test that brief is valid markdown."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Apple Inc.",
            "leverage_analysis",
            self.leverage_metrics,
        )

        # Check markdown structure
        lines = brief.split("\n")
        header_lines = [l for l in lines if l.startswith("#")]
        self.assertGreater(len(header_lines), 0)

        # Check section headers
        self.assertTrue(any("Executive Summary" in l for l in lines))
        self.assertTrue(any("Metrics" in l for l in lines))
        self.assertTrue(any("Conclusion" in l for l in lines))

    def test_brief_with_unsupported_metrics(self):
        """Test brief generation when some metrics are unsupported."""
        metrics = VerifiedMetricsSet(
            company_name="Test Corp",
            fiscal_years=[2023, 2024],
            metrics={
                2023: [
                    MetricResult("debt", 2023, 100.0, "USD M", "verified", "XBRL"),
                    MetricResult("unknown", 2023, None, "USD M", "unsupported", "XBRL"),
                ],
                2024: [
                    MetricResult("debt", 2024, 110.0, "USD M", "verified", "XBRL"),
                ],
            },
        )

        gen = BriefGenerator()
        brief = gen.generate_brief("Test Corp", "debt_liquidity", metrics)

        self.assertIn("unsupported", brief)

    def test_brief_includes_evidence_narrative(self):
        """Test that optional evidence narrative is included."""
        evidence_text = "Evidence from 10-K filing shows increased debt from operations."
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
            evidence_narrative=evidence_text,
        )

        self.assertIn("Evidence Analysis", brief)
        self.assertIn(evidence_text, brief)

    def test_brief_footer_standard(self):
        """Test that brief has standard footer disclaimer."""
        gen = BriefGenerator()
        brief = gen.generate_brief(
            "Ford Motor Company",
            "debt_liquidity",
            self.ford_metrics,
        )

        self.assertIn("deterministic numeric verification", brief)

    def test_multiple_companies_multiple_themes(self):
        """Test that generator works for different companies/themes."""
        gen = BriefGenerator()

        # Ford debt/liquidity
        brief1 = gen.generate_brief("Ford", "debt_liquidity", self.ford_metrics)
        self.assertIn("Ford", brief1)
        self.assertIn("debt", brief1.lower())

        # Apple leverage
        brief2 = gen.generate_brief("Apple", "leverage_analysis", self.leverage_metrics)
        self.assertIn("Apple", brief2)
        self.assertIn("leverage", brief2.lower())

        # Both should be valid markdown
        self.assertGreater(len(brief1), 100)
        self.assertGreater(len(brief2), 100)


if __name__ == "__main__":
    unittest.main()
