# Verified Credit Research Agent

LLM-driven ReAct agent for SEC filing-based credit research, with deterministic financial verification and auditable workpaper traces.

This project is a narrow, demo-ready credit research harness for one question:

> How did Ford's debt and liquidity risk change from 2023 to 2025, and what evidence supports the change?

It is not a generic SEC chatbot and not an investment recommendation engine. The goal is to demonstrate an auditable agent workflow for debt and liquidity risk research over SEC filings.

## Milestone Evolution

**M1: rule-based retrieval loop**

- SEC filing ingestion for Ford 2023 and 2025 filings.
- Section-aware chunking.
- BM25 plus dense vector retrieval.
- RRF fusion and reranking.
- Evidence sufficiency checks.
- Query rewrite and re-retrieval.
- Cited final answer and trace log.

**M2: deterministic numeric verification + memory / skill + evaluation**

- XBRL-first debt fact extraction.
- Text-based extraction for liquidity metrics where appropriate.
- Deterministic numeric claim verification.
- Verified numeric conclusions written back into the brief.
- Research memory and debt/liquidity skill behavior.
- Evaluation metrics and workpaper artifacts.

**M3: LLM-driven ReAct agent**

- Bedrock Claude tool calling.
- LLM query rewrite with deterministic fallback.
- LLM synthesis bounded by verified facts.
- ReAct controller that calls deterministic tools.
- Numeric guardrails that block unsupported financial numbers.
- Dual critic: deterministic numeric guardrail plus LLM semantic critic.
- Workpaper trace with `reasoning_summary` and `decision_basis`, not raw chain-of-thought.

**M4: demo UI and MCP integration**

- Static Streamlit UI over committed M3 release artifacts.
- Minimal read-only MCP server for retrieval and numeric verification.

**M5: universal SEC companyfacts analysis**

- Live SEC ticker lookup and submissions metadata parsing.
- Structured SEC `companyfacts` retrieval for deterministic XBRL facts.
- Universal analyzer for ticker/theme/year numeric analysis.
- Verified change tables and metric-level analyst notes.
- Streamlit Research Console for live SEC companyfacts analysis.
- Multi-company live smoke validation for AAPL, TSLA, and NVDA.

## M3 Demo Results

The M3 demo was run with real Bedrock tool calling and passed through Phase 5.

| Metric | Result |
|---|---:|
| `phase2_numeric_guardrail` | `block` |
| `phase2_repaired` | `true` |
| `phase3_fallback_used` | `false` |
| `phase4_tool_call_count` | `9` |
| `final_answer_numeric_guardrail` | `pass` |
| blocked claims | `0` |
| `phase5_semantic_approved` | `true` |
| tests | `35 passed` |

The Phase 4 ReAct loop made these tool calls:

- `query_memory`
- `hybrid_retrieve`
- `verify_numeric_claim` five times
- `numeric_guardrail_check`
- `write_workpaper`

## Neurosymbolic Boundary

The project deliberately separates LLM judgment from deterministic financial controls.

**LLM responsibilities**

- Interpret the research question.
- Plan and steer the ReAct loop.
- Rewrite retrieval queries.
- Synthesize credit analysis.
- Perform semantic critique.

**Deterministic Python tool responsibilities**

- Execute retrieval.
- Rerank and return evidence.
- Extract and verify numeric facts.
- Calculate changes.
- Enforce numeric guardrails.
- Persist traces and workpaper artifacts.

The LLM must not invent or calculate financial numbers. Numeric claims in the final answer must be supported by retrieved SEC filing evidence and verified deterministic outputs, or they are blocked/removed.

## Architecture

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

See [docs/architecture.md](docs/architecture.md) for a concise architecture summary.

## M5 Live SEC Validation

M5 adds deterministic live SEC companyfacts analysis. This path does not call Bedrock and does not replace the M3 ReAct agent; it is a structured numeric analysis layer for ticker-based demos.

Run the live smoke check when SEC network access is available:

```bash
python3 scripts/run_m5_live_smoke.py --json-output examples/m5_live_smoke.json
```

Latest smoke result:

| Ticker | Theme | Years | Status | Metrics | Verified Changes |
|---|---|---:|---|---:|---|
| AAPL | `leverage_analysis` | 2023, 2024 | success | 9 | yes |
| TSLA | `leverage_analysis` | 2023, 2024 | success | 9 | yes |
| NVDA | `leverage_analysis` | 2024, 2025 | success | 9 | yes |

See [M5_RELEASE_NOTES.md](M5_RELEASE_NOTES.md) and [examples/m5_live_smoke.json](examples/m5_live_smoke.json).

## M3 Demo Artifacts

The release demo artifacts are copied into [examples/m3_full_demo](examples/m3_full_demo):

- [final_answer.md](examples/m3_full_demo/final_answer.md)
- [trace_log.json](examples/m3_full_demo/trace_log.json)
- [phase4_react_tool_trace.json](examples/m3_full_demo/phase4_react_tool_trace.json)
- [final_answer_numeric_guardrail.json](examples/m3_full_demo/final_answer_numeric_guardrail.json)
- [phase5_semantic_critic.json](examples/m3_full_demo/phase5_semantic_critic.json)

The original run artifacts remain under `runs/m3_full_demo/`.

## Streamlit Demo UI

M4 adds a lightweight Streamlit presentation layer over the frozen M3 release artifacts. M5 extends the same UI with an optional live SEC companyfacts mode for ticker-based numeric analysis.

Run:

```bash
streamlit run streamlit_app.py
```

The default UI mode is static artifact mode. It loads files from `examples/m3_full_demo/` and does not require Bedrock credentials or SEC network access.

The left sidebar provides primary module navigation. The **Research Console** module accepts a ticker, risk theme, and fiscal years, then retrieves structured SEC `companyfacts` data for deterministic metric extraction. This mode does not call Bedrock by default, but it does require network access to `sec.gov`.

The Research Console also includes an optional **Generate detailed LLM stage workpaper** mode. When enabled, Bedrock generates stage-level analyst notes after deterministic SEC/XBRL extraction for intake/scoping, fact verification review, credit risk interpretation, and reviewer follow-up questions. The LLM workpaper is guarded: financial-number lines are checked against verified facts and unsupported numeric lines are removed before display.

The UI shows:

- Control Room operating dashboard.
- Why this is not a normal RAG bot.
- Optional live SEC companyfacts analysis by ticker through the Research Console.
- Optional guarded LLM stage workpaper for a more detailed analyst-style work product.
- Final credit research brief.
- M3 trace metrics and Phase 4 ReAct tool ledger.
- Numeric guardrail result and semantic critic result.
- System architecture flow.

See [docs/ui_demo.md](docs/ui_demo.md) for UI details.

## M4 Minimal MCP Server

M4.3 adds a real, minimal MCP server as a post-M3 integration layer. It is read-only and currently supports the Ford demo scope only.

Start the server:

```bash
python3 -m credit_research_agent.mcp.server
```

Exposed tools:

- `hybrid_retrieve`: searches Ford SEC filing evidence through the existing M3 retrieval pipeline.
- `verify_numeric_claim`: verifies a Ford debt/liquidity metric through the existing deterministic M3 verification path.

The MCP layer does not expose the LLM synthesizer, semantic critic, full ReAct loop, or live Bedrock demo runner.

See [docs/mcp.md](docs/mcp.md) for tool schemas and usage.

## Local Verification

Run the test suite:

```bash
python3 -m unittest discover tests
```

The M3 release package was verified with:
Current full suite:

```text
Ran 128 tests
OK (skipped=14)
```

The skipped tests are live SEC integration checks that require network access to `sec.gov`.

## Disclaimer

This project is for engineering and research demonstration only. It is not financial advice, investment advice, credit rating advice, or a recommendation to buy, sell, hold, lend to, or transact in any security or issuer.
