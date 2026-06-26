"""Run workspace creation for auditable Milestone 1 artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from credit_research_agent.config import DEFAULT_RUN_ID, RUNS_DIR
from credit_research_agent.schemas import Plan, TaskSpec, write_json


ARTIFACT_FILENAMES = {
    "task": "task.md",
    "task_spec": "task_spec.json",
    "plan": "plan.json",
    "retrieved_chunks": "retrieved_chunks.json",
    "reranked_chunks": "reranked_chunks.json",
    "evidence_table": "evidence_table.json",
    "evidence_coverage": "evidence_coverage.json",
    "query_rewrites": "query_rewrites.json",
    "numeric_facts": "numeric_facts.json",
    "numeric_claims": "numeric_claims.json",
    "numeric_verification": "numeric_verification.json",
    "evaluation_summary": "evaluation_summary.json",
    "critic_report": "critic_report.json",
    "trace_log": "trace_log.json",
    "final_answer": "final_answer.md",
    "memory_update": "memory_update.json",
}


@dataclass(frozen=True)
class RunWorkspace:
    run_id: str
    root: Path

    @property
    def artifacts(self) -> dict[str, Path]:
        return {
            name: self.root / filename
            for name, filename in ARTIFACT_FILENAMES.items()
        }

    def artifact_path(self, name: str) -> Path:
        try:
            return self.artifacts[name]
        except KeyError as exc:
            raise KeyError(f"Unknown artifact name: {name}") from exc

    def relative_artifacts(self) -> dict[str, str]:
        return {name: str(path) for name, path in self.artifacts.items()}

    def write_task(self, question: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifact_path("task").write_text(question + "\n", encoding="utf-8")

    def write_task_spec(self, task_spec: TaskSpec) -> None:
        write_json(self.artifact_path("task_spec"), task_spec)

    def write_plan(self, plan: Plan) -> None:
        write_json(self.artifact_path("plan"), plan)


def create_run_workspace(
    run_id: str = DEFAULT_RUN_ID,
    runs_dir: Path = RUNS_DIR,
) -> RunWorkspace:
    """Create the run workspace directory and return artifact helpers."""

    workspace = RunWorkspace(run_id=run_id, root=runs_dir / run_id)
    workspace.root.mkdir(parents=True, exist_ok=True)
    return workspace
