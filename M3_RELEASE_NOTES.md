# M3 Release Notes

## What Changed in M3

M3 upgrades the verified credit research harness from deterministic retrieval and verification into an LLM-driven ReAct agent. The LLM now participates in planning, query rewriting, synthesis, and semantic critique while deterministic Python tools continue to enforce retrieval execution, numeric verification, guardrails, and trace persistence.

M3 does not implement MCP. MCP remains future roadmap work.

## Key Capabilities

- Real Bedrock Claude tool-calling loop.
- Deterministic tool registry for retrieval, memory, numeric verification, numeric guardrail checks, and workpaper writes.
- LLM-primary query rewrite with deterministic fallback.
- LLM synthesizer bounded by verified numeric facts.
- Numeric guardrail that blocks unsupported financial numbers while ignoring metadata such as years and counts.
- ReAct loop that calls memory, hybrid retrieval, numeric verification, guardrail, and workpaper tools.
- Dual critic with deterministic numeric checking and LLM semantic review.
- Trace logs with `reasoning_summary` and `decision_basis`, not raw private reasoning.

## Demo Results

The Ford debt/liquidity M3 demo passed through Phase 5 with these metrics:

```json
{
  "final_answer_numeric_guardrail": "pass",
  "phase2_numeric_guardrail": "block",
  "phase2_repaired": true,
  "phase3_fallback_used": false,
  "phase4_numeric_guardrail": "pass",
  "phase4_tool_call_count": 9,
  "phase5_repair_guardrail": "not_run",
  "phase5_semantic_approved": true
}
```

The full test suite passed:

```text
Ran 35 tests
OK
```

## Guardrail Behavior

The Phase 2 LLM draft included unsupported or insufficiently tagged financial numbers. The deterministic numeric guardrail blocked those claims, and the system repaired the answer before finalization.

The final packaged answer passed numeric guardrail review:

- `final_answer_numeric_guardrail = pass`
- `blocked_count = 0`
- all checked financial numbers were bound to verified claim IDs

This demonstrates the intended boundary: the LLM may write analysis, but deterministic tools control which financial numbers survive into the final brief.

## Artifact List

Packaged demo artifacts are in `examples/m3_full_demo/`:

- `final_answer.md`
- `trace_log.json`
- `phase4_react_tool_trace.json`
- `final_answer_numeric_guardrail.json`
- `phase5_semantic_critic.json`

Original run artifacts remain in `runs/m3_full_demo/`.

## Known Limitations

- The first demo is intentionally narrow: Ford debt/liquidity risk from 2023 to 2025.
- The agent is not a general SEC filing chatbot.
- The system does not provide investment advice, ratings, forecasts, or buy/sell/hold recommendations.
- Numeric verification is strongest for mapped XBRL debt facts and explicitly extracted liquidity metrics.
- Some management explanations remain qualitative and depend on retrieved filing chunks.
- ReAct behavior is demonstrated through the Ford workflow only.
- MCP is not implemented in M3.

## Next Roadmap

- Package a lightweight MCP server as future work, exposing only:
  - `hybrid_retrieve`
  - `verify_numeric_claim`
- Add a small demo UI after the CLI/workpaper path remains stable.
- Add more companies and risk themes only after the Ford workflow remains reliable.
- Expand evaluation beyond the current deterministic metrics after the core harness is stable.
