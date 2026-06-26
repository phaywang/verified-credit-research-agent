"""Trace logging for agent state transitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from credit_research_agent.schemas import FinalMetrics, TraceLog, TraceStep, write_json


class TraceLogger:
    """Append-only trace logger for one run."""

    def __init__(
        self,
        run_id: str,
        task: str,
        task_spec_path: str,
        artifacts: Optional[Dict[str, str]] = None,
    ) -> None:
        self.trace = TraceLog(
            run_id=run_id,
            task=task,
            task_spec_path=task_spec_path,
            artifacts=artifacts or {},
        )

    def log_step(self, step: TraceStep) -> None:
        self.trace.steps.append(step)

    def log_failure(
        self,
        state: str,
        error: BaseException,
        summary: str = "Run failed.",
        **extra: Any,
    ) -> None:
        self.trace.status = "failed"
        self.log_step(
            TraceStep(
                state=state,
                summary=summary,
                error={
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
                **extra,
            )
        )

    def finalize(
        self,
        metrics: FinalMetrics,
        loop_iterations: int,
        status: str = "completed",
    ) -> None:
        self.trace.final_metrics = metrics
        self.trace.loop_iterations = loop_iterations
        self.trace.status = status  # type: ignore[assignment]

    def write(self, path: Path) -> None:
        write_json(path, self.trace)
