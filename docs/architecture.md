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
-> Statement Table Extraction
-> Companyfacts Cross-check / Fallback
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
- SEC 10-K statement table extraction from HTML / inline XBRL.
- Statement-first metric resolution.
- SEC companyfacts cross-checking and fallback.
- Numeric change calculations.
- Numeric claim verification.
- Guardrail enforcement for unsupported financial numbers.
- Workpaper and trace persistence.

## Why This Boundary Matters

Credit research requires language judgment, but financial numbers must be controlled. The LLM can explain the credit story while Python tools decide whether numeric claims are verified, statement-derived, cross-checked, unsupported, inconsistent, low confidence, or blocked.

The final trace stores audit-safe summaries such as `reasoning_summary` and `decision_basis`. It does not store raw private reasoning.
