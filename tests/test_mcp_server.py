import asyncio
import unittest

from credit_research_agent.mcp.server import (
    build_server,
    hybrid_retrieve_tool,
    verify_numeric_claim_tool,
)


class MCPServerTests(unittest.TestCase):
    def test_mcp_tool_schema_exists(self):
        async def list_tool_names():
            server = build_server()
            tools = await server.list_tools()
            return {tool.name for tool in tools}

        names = asyncio.run(list_tool_names())
        self.assertEqual(names, {"hybrid_retrieve", "verify_numeric_claim"})

    def test_hybrid_retrieve_returns_real_ford_chunk(self):
        response = hybrid_retrieve_tool(
            query="Ford 2025 debt liquidity credit facilities",
            top_n=3,
            filters={"ticker": "F", "years": [2025]},
        )
        self.assertGreaterEqual(len(response["results"]), 1)
        first = response["results"][0]
        for field in ["chunk_id", "fiscal_year", "section_name", "text", "citation", "score"]:
            self.assertIn(field, first)
        self.assertEqual(first["fiscal_year"], 2025)
        self.assertLessEqual(len(first["text"]), 700)

    def test_verify_numeric_claim_returns_verified_known_metric(self):
        response = verify_numeric_claim_tool(
            ticker="F",
            metric_name="company_debt_payable_within_one_year",
            old_year=2023,
            new_year=2025,
        )
        self.assertEqual(response["status"], "verified")
        self.assertEqual(response["old_value"], 0.477)
        self.assertEqual(response["new_value"], 5.55)
        self.assertEqual(response["absolute_change"], 5.073)
        self.assertIn(
            "ford_2025_company_debt_payable_within_one_year_xbrl_high",
            response["source_fact_ids"],
        )

    def test_non_ford_ticker_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_numeric_claim_tool(
                ticker="TSLA",
                metric_name="company_debt_payable_within_one_year",
                old_year=2023,
                new_year=2025,
            )


if __name__ == "__main__":
    unittest.main()

