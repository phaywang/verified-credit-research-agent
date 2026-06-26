import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.agent.planner import create_plan
from credit_research_agent.agent.task_parser import parse_task


class PlannerTest(unittest.TestCase):
    def test_create_plan_includes_query_and_loop_limit(self):
        spec = parse_task(
            "How did Ford's debt and liquidity risk change from 2023 to 2025, "
            "and what evidence supports the change?"
        )
        plan = create_plan(spec)

        self.assertEqual(plan.max_retrieval_iterations, 3)
        self.assertIn("Ford 2023 2025 10-K", plan.initial_query)
        self.assertIn("credit facilities", plan.initial_query)
        self.assertGreaterEqual(len(plan.research_steps), 5)


if __name__ == "__main__":
    unittest.main()

