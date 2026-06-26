import unittest

from credit_research_agent.m3.query_rewriter import parse_rewrite_json


class M3QueryRewriterTests(unittest.TestCase):
    def test_parse_json_from_fenced_response(self):
        parsed = parse_rewrite_json(
            """```json
            {
              "rewritten_query": "Ford 2025 10-K MD&A liquidity management explanation",
              "reasoning_summary": "Targets missing management explanation.",
              "target_years": [2025],
              "target_sections": ["MD&A"],
              "fallback_used": false
            }
            ```"""
        )
        self.assertEqual(parsed["target_years"], [2025])
        self.assertFalse(parsed["fallback_used"])


if __name__ == "__main__":
    unittest.main()
