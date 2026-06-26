# Milestone 4 Technical Design

## 1. Scope and Non-Goals

### Goal

Milestone 4 adds presentation and integration layers on top of the completed M3 runtime:

1. A minimal real MCP server.
2. A lightweight Streamlit demo UI.
3. GitHub / resume / interview packaging that makes the M3 agent easy to inspect.

M4 is a wrapper and packaging milestone. It must not rebuild the M3 ReAct agent or modify financial verification behavior.

### In Scope

- Static demo UI that loads `examples/m3_full_demo/` artifacts.
- Optional live UI mode that runs `scripts/run_m3_full_demo.py` only when credentials are available.
- Minimal MCP server exposing selected deterministic M3 tools:
  - `hybrid_retrieve`
  - `verify_numeric_claim`
- Documentation for UI and MCP usage.
- MCP tests for schema and local tool execution.
- Existing test suite preservation.

### Non-Goals

- No rewrite of the M3 ReAct agent core.
- No change to numeric verification logic.
- No weakening of guardrails.
- No multi-company support.
- No new financial risk themes.
- No database.
- No authentication.
- No complex charts.
- No MCP claim in resume bullets until a real server is implemented and tested.
- No changes to `.claude/settings.json`.

## 2. MCP Server Design

### Design Principle

The MCP server is an integration layer over existing M3 deterministic tools. It should call the same code paths used by the M3 tool registry rather than duplicating retrieval or verification logic.

Preferred source functions:

- `credit_research_agent.m3.deterministic_tools.hybrid_retrieve`
- `credit_research_agent.m3.deterministic_tools.verify_numeric_claim`

### Proposed File Layout

```text
src/credit_research_agent/mcp/
  __init__.py
  server.py
  schemas.py

tests/
  test_mcp_server.py

docs/
  mcp.md
```

If the MCP SDK conventions are simpler with a single module, use:

```text
src/credit_research_agent/mcp_server.py
```

The package layout is preferred because it separates server wiring from input/output schemas.

### Tools

#### `hybrid_retrieve`

Purpose: retrieve SEC filing evidence chunks using the existing M3 retrieval pipeline.

Input:

```json
{
  "query": "Ford 2025 debt liquidity credit facilities",
  "top_n": 10,
  "filters": {
    "ticker": "F",
    "years": [2023, 2025],
    "sections": ["liquidity", "debt", "credit_facilities"]
  }
}
```

Output:

```json
{
  "results": [
    {
      "chunk_id": "F_2025_10K_credit_facilities_002",
      "fiscal_year": 2025,
      "section_name": "Other unsecured credit facilities",
      "text": "...",
      "citation": "https://www.sec.gov/...",
      "score": 0.031
    }
  ]
}
```

Implementation notes:

- Internally call `m3.deterministic_tools.hybrid_retrieve(query, top_n)`.
- First implementation may support only `ticker = "F"`, but the schema is future-proof.
- Optional filters should be accepted by the MCP schema even if only lightly applied in M4.3.
- Normalize the M3 result shape to MCP-friendly fields.
- Keep text previews bounded to avoid giant MCP payloads.
- Do not write artifacts.

#### `verify_numeric_claim`

Purpose: verify a debt/liquidity-related metric across two years using deterministic M3 verification logic.

Input:

```json
{
  "ticker": "F",
  "metric_name": "company_debt_payable_within_one_year",
  "old_year": 2023,
  "new_year": 2025
}
```

Output:

```json
{
  "status": "verified",
  "old_value": 0.477,
  "new_value": 5.55,
  "absolute_change": 5.073,
  "percentage_change": 1063.52,
  "source_fact_ids": [
    "ford_2023_company_debt_payable_within_one_year_xbrl_high",
    "ford_2025_company_debt_payable_within_one_year_xbrl_high"
  ]
}
```

Implementation notes:

- Internally call `m3.deterministic_tools.verify_numeric_claim(metric_name, old_year, new_year)`.
- First implementation may support only `ticker = "F"`.
- Preserve status values from M3:
  - `verified`
  - `unsupported`
  - `low_confidence`
  - `not_enough_data`
  - `inconsistent`
- Do not recompute values in the MCP layer.

### MCP Runtime Choice

Use the standard Python MCP SDK if available and lightweight. If dependency uncertainty is high, M4.3 should first validate installation and import of the SDK before implementation.

The design should avoid introducing a custom protocol shim that only resembles MCP. The resume should claim MCP only after a real MCP server starts locally and tools execute through it.

### Read-Only Safety

Default MCP tools are read-only / analysis-only:

- `hybrid_retrieve`: read-only.
- `verify_numeric_claim`: read-only.
- No first-version MCP write tools.

No tool should expose secrets, environment variables, API keys, or raw `.env` content.

## 3. UI Design

### Design Principle

The UI is a recruiter/interviewer demo surface. It should make the completed M3 system understandable without requiring live Bedrock credentials.

Static artifact mode must work out of the box.

### Proposed File Layout

```text
streamlit_app.py

docs/
  ui_demo.md
```

Use `streamlit_app.py` as the preferred entrypoint:

```bash
streamlit run streamlit_app.py
```

### UI Sections

#### Home / Overview

Show:

- Project title: `Verified Credit Research Agent`
- One-line description:
  `LLM-driven ReAct agent for SEC filing-based credit research, with deterministic financial verification and auditable traces.`
- Short M1 / M2 / M3 evolution:
  - M1: rule-based retrieval loop.
  - M2: deterministic numeric verification + memory / skill + evaluation.
  - M3: Bedrock ReAct agent + query rewrite + synthesis + dual critic + numeric guardrails.
- Short section: `Why this is not a normal RAG bot`
  - Explain that the system uses an LLM-driven ReAct loop, Bedrock tool calling, deterministic numeric verification, guardrail repair, dual critic review, and auditable traces.

#### Demo Runner

Controls:

- Mode indicator:
  - `Static demo artifact mode`
  - `Live Bedrock mode`
- Button:
  - `Load M3 Demo Artifacts`

Behavior:

- Static mode loads files from `examples/m3_full_demo/`.
- M4.2 implements static mode only.
- Live mode is future M4.4 work and should not be implemented in M4.2.

#### Final Brief Viewer

Render:

- `examples/m3_full_demo/final_answer.md`

#### Trace Viewer

Show key metrics from:

- `examples/m3_full_demo/trace_log.json`

Required fields:

- `phase2_numeric_guardrail = block`
- `phase2_repaired = true`
- `phase3_fallback_used = false`
- `phase4_tool_call_count = 9`
- `final_answer_numeric_guardrail = pass`
- `blocked claims = 0`
- `phase5_semantic_approved = true`

#### Tool Call Timeline

Source:

- `examples/m3_full_demo/phase4_react_tool_trace.json`

Show each tool call with:

- tool name
- input summary
- output summary
- status

Keep output summaries compact. Avoid dumping huge retrieval text by default.

#### Guardrail Viewer

Source:

- `examples/m3_full_demo/final_answer_numeric_guardrail.json`

Highlight:

- `severity = pass`
- `blocked_count = 0`

Allow optional JSON expansion.

#### Semantic Critic Viewer

Source:

- `examples/m3_full_demo/phase5_semantic_critic.json`

Highlight:

- `approved = true`
- `reasoning_summary`
- issues and repair suggestions as review notes, not blockers.

#### Architecture Tab

Show the M4/M3 flow:

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

### UI Constraints

- No authentication.
- No database.
- No multi-company support.
- No new risk themes.
- No API key display.
- No requirement for Bedrock credentials in static mode.
- No complex custom styling needed.

## 4. File Structure

Expected M4 additions:

```text
streamlit_app.py

docs/
  ui_demo.md
  mcp.md

src/credit_research_agent/mcp/
  __init__.py
  server.py
  schemas.py

tests/
  test_mcp_server.py
```

Existing M3 files remain frozen:

```text
src/credit_research_agent/m3/
scripts/run_m3_full_demo.py
examples/m3_full_demo/
```

M4 may import from M3 but should not modify M3 runtime behavior unless a tiny compatibility helper is unavoidable and reviewed.

## 5. How M4 Wraps Existing M3

M4 integration must be thin:

- UI reads committed static artifacts from `examples/m3_full_demo/`.
- Optional future live UI mode may shell out to the existing `scripts/run_m3_full_demo.py` rather than reimplementing the pipeline.
- MCP tools call existing M3 deterministic wrappers.
- MCP does not expose the LLM synthesizer or critic as tools.
- MCP does not recompute numeric values.
- MCP does not bypass numeric guardrails.
- M4.3 MCP remains read-only and exposes only `hybrid_retrieve` and `verify_numeric_claim`.

The boundary remains:

- LLM roles live in M3.
- deterministic verification and guardrails live in M3/M2.
- M4 exposes and visualizes them.

## 6. Testing Plan

### Before M4 Implementation

Run:

```bash
python3 -m unittest discover tests
```

Expected baseline:

```text
35 tests OK
```

### M4.2 UI Static Mode

Manual verification is acceptable for Streamlit rendering:

```bash
streamlit run streamlit_app.py
```

Check:

- App starts.
- Static mode is visible.
- final brief renders.
- trace metrics render.
- tool timeline renders.
- guardrail status is pass / blocked count zero.
- semantic critic approved is visible.

Automated tests only if meaningful. Avoid brittle Streamlit UI tests.

### M4.3 MCP Server

Add `tests/test_mcp_server.py`.

Test coverage:

- MCP tool schema definitions exist.
- `hybrid_retrieve` wrapper returns at least one real Ford filing chunk.
- `verify_numeric_claim` returns `verified` for a known metric such as `company_debt_payable_within_one_year`.
- output includes expected fields.
- no raw runs directories are required.

### Regression Tests

After each M4 phase:

```bash
python3 -m unittest discover tests
```

Existing tests must not be weakened or rewritten merely to pass.

## 7. Risks and Mitigations

### Risk: MCP SDK dependency friction

Mitigation:

- Validate SDK installation/import before implementation.
- Keep MCP server minimal.
- Do not claim MCP in resume until server starts and tools execute.

### Risk: UI accidentally requires Bedrock credentials

Mitigation:

- Static mode is default.
- Live mode is optional and gated.
- Missing credentials should show a user-facing fallback message.

### Risk: M4 duplicates M3 logic

Mitigation:

- Import M3 deterministic wrappers.
- Keep MCP and UI as presentation/integration layers.
- Avoid new calculation code.

### Risk: raw run artifacts bloat git history

Mitigation:

- Commit curated `examples/m3_full_demo/`.
- Do not commit raw `runs/` directories.

### Risk: guardrails look optional in UI

Mitigation:

- Guardrail status should be prominent.
- Show `phase2_numeric_guardrail = block` and `phase2_repaired = true`.
- Show final `blocked_count = 0`.

### Risk: overstating financial conclusion

Mitigation:

- Keep final artifact text as M3-approved.
- Do not add new financial claims in UI.
- Include "not financial advice" disclaimer.

## 8. Definition of Done

### M4.2 UI Static Mode

- `streamlit run streamlit_app.py` starts.
- Static demo mode works without Bedrock credentials.
- Final answer is viewable.
- trace metrics are visible.
- tool call timeline is visible.
- guardrail and semantic critic results are visible.
- README and `docs/ui_demo.md` explain usage.
- Existing tests still pass.

### M4.3 Minimal MCP Server

- MCP server starts locally.
- `hybrid_retrieve` returns real retrieval results.
- `verify_numeric_claim` returns deterministic verification output.
- MCP tests pass.
- `docs/mcp.md` explains usage.
- README clearly labels MCP as a post-M3 integration layer.
- No M3 core behavior is changed.

### M4.4 Optional Live UI Mode

- UI can run the M3 full demo when Bedrock credentials are available.
- UI falls back to static artifact mode when credentials are missing.
- No secrets are displayed.
- Existing tests still pass.

## 9. Recommended Implementation Order

### Phase M4.1: Design Only

- Create this M4 technical design document.
- Stop for review.

### Phase M4.2: UI Static Demo Mode

- Add `streamlit_app.py`.
- Load only `examples/m3_full_demo/`.
- Add `docs/ui_demo.md`.
- Update README with UI instructions.
- Run tests.

### Phase M4.3: Minimal MCP Server

- Validate MCP SDK availability.
- Add MCP server with `hybrid_retrieve` and `verify_numeric_claim`.
- Add `tests/test_mcp_server.py`.
- Add `docs/mcp.md`.
- Update README.
- Run tests.

### Phase M4.4: Optional Live UI Mode

- Add a live demo button.
- Check credentials before invoking Bedrock.
- Fall back to static mode on missing credentials or runtime failure.
- Run tests and manually verify UI.

## 10. Commit Plan

Use separate commits where possible:

### Commit 1

```text
Add M4 static Streamlit demo UI
```

Likely files:

```text
streamlit_app.py
docs/ui_demo.md
README.md
```

### Commit 2

```text
Add minimal MCP server for retrieval and numeric verification
```

Likely files:

```text
src/credit_research_agent/mcp/
tests/test_mcp_server.py
docs/mcp.md
README.md
pyproject.toml
```

### Commit 3

```text
Update M4 demo and MCP documentation
```

Likely files:

```text
README.md
docs/ui_demo.md
docs/mcp.md
```

Do not stage:

```text
.claude/settings.json
runs/m3_full_demo/
runs/m3_phase1_tool_gate/
__pycache__/
.env
local credentials
```
