import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.agent.task_parser import parse_task


class TaskParserTest(unittest.TestCase):
    def test_parse_supported_ford_question(self):
        spec = parse_task(
            "How did Ford's debt and liquidity risk change from 2023 to 2025, "
            "and what evidence supports the change?"
        )

        self.assertEqual(spec.company, "Ford Motor Company")
        self.assertEqual(spec.ticker, "F")
        self.assertEqual(spec.cik, "0000037996")
        self.assertEqual(spec.years, [2023, 2025])
        self.assertEqual(spec.filing_types, ["10-K"])
        self.assertEqual(spec.risk_theme, "debt_liquidity")
        self.assertIn("management explanation", spec.required_evidence)

    def test_rejects_unsupported_question(self):
        with self.assertRaises(ValueError):
            parse_task("How did Tesla liquidity change in 2024?")


if __name__ == "__main__":
    unittest.main()

