# Architecture

Verified Credit Research Agent uses a neurosymbolic architecture: LLM roles steer research, while deterministic Python tools enforce evidence, calculations, numeric verification, guardrails, and traceability.

## Flow

```text
User Question
-> Task Spec Parser
-> Memory Reader
-> Skill Loader
-> LLM Planner / ReAct Loop
-> Tool Layer
-> Hybrid Retrieval / Reranking
-> Numeric Verification
-> LLM Synthesizer
-> Numeric Guardrail
-> Dual Critic
-> Workpaper Trace
-> Final Credit Research Brief
```

## Role Separation

The LLM handles:

- Research planning.
- Retrieval steering.
- Query rewriting.
- Evidence-aware synthesis.
- Semantic critique.

Deterministic Python handles:

- Filing retrieval and chunk lookup.
- Hybrid retrieval and reranking.
- XBRL-first fact extraction.
- Numeric change calculations.
- Numeric claim verification.
- Guardrail enforcement for unsupported financial numbers.
- Workpaper and trace persistence.

## Why This Boundary Matters

Credit research requires language judgment, but financial numbers must be controlled. M3 allows the LLM to explain the credit story while Python tools decide whether numeric claims are verified, unsupported, inconsistent, low confidence, or blocked.

The final trace stores audit-safe summaries such as `reasoning_summary` and `decision_basis`. It does not store raw private reasoning.
