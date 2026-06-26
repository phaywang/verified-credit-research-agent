import unittest

from credit_research_agent.m3.guardrails import (
    extract_financial_numbers,
    numeric_guardrail_check,
    strip_unverified_financial_lines,
)


class M3GuardrailTests(unittest.TestCase):
    def test_ignores_years_and_counts_but_captures_financial_numbers(self):
        text = "In 2023 and 2025, two filings showed debt of $19.944B and +9.90%."
        numbers = [item.text for item in extract_financial_numbers(text)]
        self.assertEqual(numbers, ["$19.944B", "+9.90%"])

    def test_passes_same_line_verified_binding(self):
        verified = [{"claim_id": "claim_debt", "status": "verified"}]
        report = numeric_guardrail_check(
            "Debt rose from $19.944B to $21.919B. [verified: claim_debt]",
            verified,
        )
        self.assertEqual(report["severity"], "pass")
        self.assertEqual(report["blocked_count"], 0)

    def test_blocks_unverified_financial_line_and_repairs(self):
        verified = [{"claim_id": "claim_debt", "status": "verified"}]
        text = "Debt was $19.944B.\nThe company had $99.000B of extra liquidity."
        report = numeric_guardrail_check(text, verified)
        self.assertEqual(report["severity"], "block")
        repaired = strip_unverified_financial_lines(text, report)
        self.assertNotIn("$99.000B", repaired)


if __name__ == "__main__":
    unittest.main()
