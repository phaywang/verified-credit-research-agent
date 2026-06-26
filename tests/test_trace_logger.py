import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.schemas import FinalMetrics, TraceStep
from credit_research_agent.workpapers.trace_logger import TraceLogger


class TraceLoggerTest(unittest.TestCase):
    def test_trace_logger_writes_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "trace_log.json"
            logger = TraceLogger(
                run_id="ford_debt_liquidity_2023_2025",
                task="question",
                task_spec_path="runs/demo/task_spec.json",
                artifacts={"final_answer": "runs/demo/final_answer.md"},
            )
            logger.log_step(
                TraceStep(
                    state="PLAN",
                    summary="Created plan.",
                    outputs={"plan_path": "runs/demo/plan.json"},
                )
            )
            logger.finalize(
                FinalMetrics(
                    citation_coverage=1.0,
                    evidence_coverage_passed=True,
                    retrieval_iterations=1,
                ),
                loop_iterations=1,
            )
            logger.write(path)

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["steps"][0]["state"], "PLAN")
            self.assertEqual(data["final_metrics"]["citation_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()

