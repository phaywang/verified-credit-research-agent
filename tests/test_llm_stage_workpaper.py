"""Tests for optional LLM stage workpaper generation."""

import unittest

from credit_research_agent.llm_stage_workpaper import (
    generate_consolidated_stage_workpaper,
    generate_stage_workpaper,
)
from credit_research_agent.sec_integration import MetricValue


class LLMStageWorkpaperTest(unittest.TestCase):
    """Test guarded stage-level LLM workpaper generation."""

    def test_generates_four_stage_workpapers(self):
        metrics = {
            2023: [
                MetricValue(
                    metric_name="total_debt",
                    value=100.0,
                    unit="USD millions",
                    fiscal_year=2023,
                    xbrl_concept="us-gaap:Debt",
                    source="SEC companyfacts",
                )
            ],
            2024: [
                MetricValue(
                    metric_name="total_debt",
                    value=110.0,
                    unit="USD millions",
                    fiscal_year=2024,
                    xbrl_concept="us-gaap:Debt",
                    source="SEC companyfacts",
                )
            ],
        }

        def fake_llm(prompt, system_prompt, max_tokens):
            return "Verified total debt changed from 100.0 to 110.0 USD millions."

        workpaper = generate_stage_workpaper(
            company="Test Corp",
            ticker="TEST",
            risk_theme="leverage_analysis",
            years=[2023, 2024],
            metrics_by_year=metrics,
            deterministic_brief="Verified brief",
            invoke_fn=fake_llm,
        )

        self.assertEqual(len(workpaper), 4)
        self.assertTrue(all(stage.status == "success" for stage in workpaper))
        self.assertTrue(all(stage.guardrail_status == "pass" for stage in workpaper))

    def test_blocks_unverified_financial_numbers(self):
        metrics = {
            2024: [
                MetricValue(
                    metric_name="cash",
                    value=50.0,
                    unit="USD millions",
                    fiscal_year=2024,
                    xbrl_concept="us-gaap:Cash",
                    source="SEC companyfacts",
                )
            ]
        }

        def fake_llm(prompt, system_prompt, max_tokens):
            return (
                "Cash was 50.0 USD millions based on verified facts.\n"
                "The company also has 999.0 USD millions of hidden liquidity."
            )

        workpaper = generate_stage_workpaper(
            company="Test Corp",
            ticker="TEST",
            risk_theme="debt_liquidity",
            years=[2024],
            metrics_by_year=metrics,
            deterministic_brief="Verified brief",
            invoke_fn=fake_llm,
        )

        self.assertEqual(workpaper[0].guardrail_status, "repaired")
        self.assertIn("50.0 USD millions", workpaper[0].analysis)
        self.assertNotIn("999.0 USD millions", workpaper[0].analysis)
        self.assertEqual(len(workpaper[0].blocked_lines), 1)

    def test_consolidated_multi_theme_workpaper_uses_single_llm_call(self):
        metrics = {
            2024: [
                MetricValue(
                    metric_name="cash",
                    value=50.0,
                    unit="USD millions",
                    fiscal_year=2024,
                    xbrl_concept="us-gaap:Cash",
                    source="SEC companyfacts",
                )
            ]
        }
        calls = []

        def fake_llm(prompt, system_prompt, max_tokens):
            calls.append(prompt)
            return (
                "## Combined risk priorities\n"
                "Cash was 50.0 USD millions based on verified facts.\n"
                "Unsupported leverage was 777.0 USD millions."
            )

        workpaper = generate_consolidated_stage_workpaper(
            company="Test Corp",
            ticker="TEST",
            risk_themes=["leverage_analysis", "debt_liquidity"],
            years=[2024],
            analyses=[
                {
                    "risk_theme": "leverage_analysis",
                    "metrics_by_year": metrics,
                    "deterministic_brief": "Leverage brief",
                },
                {
                    "risk_theme": "debt_liquidity",
                    "metrics_by_year": metrics,
                    "deterministic_brief": "Debt brief",
                },
            ],
            invoke_fn=fake_llm,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(workpaper), 1)
        self.assertEqual(workpaper[0].stage, "Consolidated Multi-Theme Workpaper")
        self.assertEqual(workpaper[0].guardrail_status, "repaired")
        self.assertIn("50.0 USD millions", workpaper[0].analysis)
        self.assertNotIn("777.0 USD millions", workpaper[0].analysis)


if __name__ == "__main__":
    unittest.main()
