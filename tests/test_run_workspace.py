import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.agent.planner import create_plan
from credit_research_agent.agent.task_parser import parse_task
from credit_research_agent.workpapers.run_workspace import create_run_workspace


class RunWorkspaceTest(unittest.TestCase):
    def test_workspace_writes_initial_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = create_run_workspace("demo", Path(tmpdir))
            question = (
                "How did Ford's debt and liquidity risk change from 2023 to 2025, "
                "and what evidence supports the change?"
            )
            spec = parse_task(question)
            plan = create_plan(spec)

            workspace.write_task(question)
            workspace.write_task_spec(spec)
            workspace.write_plan(plan)

            self.assertTrue(workspace.artifact_path("task").exists())
            task_spec = json.loads(
                workspace.artifact_path("task_spec").read_text(encoding="utf-8")
            )
            self.assertEqual(task_spec["ticker"], "F")
            self.assertTrue(workspace.artifact_path("plan").exists())


if __name__ == "__main__":
    unittest.main()

