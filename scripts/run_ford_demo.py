"""Run the Milestone 1 Ford debt/liquidity agentic retrieval demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.agent.loop_controller import DEFAULT_QUESTION, LoopController


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--force-rewrite-demo",
        action="store_true",
        help="Use a deliberately narrow first query so the trace demonstrates query rewrite.",
    )
    args = parser.parse_args()

    workspace = LoopController(
        force_rewrite_demo=args.force_rewrite_demo,
    ).run(args.question)

    print(f"Final answer: {workspace.artifact_path('final_answer')}")
    print(f"Trace log: {workspace.artifact_path('trace_log')}")


if __name__ == "__main__":
    main()

