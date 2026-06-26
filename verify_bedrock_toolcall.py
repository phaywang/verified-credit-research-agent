#!/usr/bin/env python3
"""M3 Phase 1 gate: real Bedrock multi-turn tool-calling closure."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from credit_research_agent.m3.bedrock_client import invoke_with_tools
from credit_research_agent.m3.tool_specs import phase1_gate_registry


PROMPT = """You are testing tool calling.

Important:
- Call exactly one tool at a time.
- First call remember_step with step_name="step_1".
- After receiving that tool result, call remember_step with step_name="step_2".
- After receiving that tool result, call remember_step with step_name="step_3".
- After receiving that tool result, call summarize_steps.
- After receiving summarize_steps, provide a final concise sentence.

Do not skip steps. Do not call multiple tools in the same assistant message.
"""


def main() -> int:
    print("M3 Phase 1 Bedrock tool-calling gate\n")
    try:
        result = invoke_with_tools(
            PROMPT,
            phase1_gate_registry(),
            system_prompt=(
                "You are a strict tool-use test agent. Follow the user's sequence exactly. "
                "Call one tool per assistant turn."
            ),
            max_turns=8,
            max_tokens=1024,
        )
    except Exception as exc:
        print("GATE FAILED: Bedrock invocation did not complete.")
        print(f"{exc.__class__.__name__}: {exc}")
        print("\nIf this environment lacks AWS credentials, run this locally with:")
        print("  AWS_PROFILE=<profile> AWS_REGION=us-east-1 python3 verify_bedrock_toolcall.py")
        return 1

    tool_events = [event for event in result.events if event.kind == "tool_call"]
    print("=== Tool Events ===")
    for idx, event in enumerate(tool_events, 1):
        print(f"{idx}. tool={event.tool_name}")
        print(f"   input={json.dumps(event.tool_input, sort_keys=True)}")
        print(f"   result={json.dumps(event.tool_result, sort_keys=True)}")

    print("\n=== Final Text ===")
    print(result.final_text)
    print("\n=== Stop Reason ===")
    print(result.stop_reason)

    names = [event.tool_name for event in tool_events]
    expected_prefix = ["remember_step", "remember_step", "remember_step", "summarize_steps"]
    if names[:4] != expected_prefix:
        print("\nGATE FAILED: expected 3 remember_step calls followed by summarize_steps.")
        print(f"Observed tool sequence: {names}")
        return 1

    print("\nGATE PASSED: real Bedrock tool_use → tool_result multi-turn closure works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
