# Streamlit Demo UI

The Streamlit demo UI presents the completed M3 release artifacts and, in M5, adds an optional live SEC companyfacts analysis mode.

## Run

```bash
streamlit run streamlit_app.py
```

## Static Artifact Mode

The default UI mode is static artifact mode. It loads committed files from:

```text
examples/m3_full_demo/
```

It does not call Bedrock, run the M3 pipeline, require API credentials, or require SEC network access.

## Research Console Mode

The **Research Console** module accepts:

- company name, alias, or ticker, such as `Apple`, `JP Morgan`, `Google`, or `AAPL`
- risk theme, such as `Leverage Analysis`
- fiscal years, such as `2023, 2024`

It then runs the deterministic universal analyzer:

```text
company/ticker resolver
-> SEC ticker, CIK, and standard company name
-> SEC submissions metadata
-> SEC companyfacts JSON
-> configured XBRL concept mapping
-> verified metric extraction
-> deterministic credit brief
```

By default, this mode does not call Bedrock. It requires live access to `www.sec.gov` and `data.sec.gov`. The preset selector only loads verified demo shortcuts; users can still type any SEC EDGAR-covered public company name or ticker, subject to available companyfacts and configured XBRL concept coverage.

An optional **Generate detailed LLM stage workpaper** checkbox runs a Bedrock-backed analyst narrative after deterministic SEC/XBRL extraction. That optional mode generates stage-level workpaper notes for:

- intake and scoping
- fact verification review
- credit risk interpretation
- reviewer questions and next work

The LLM workpaper is guarded: financial-number lines are checked against verified SEC/XBRL facts, and unsupported numeric lines are removed before display.

## Live SEC Smoke Check

Before a live demo, you can validate the SEC path without opening the UI:

```bash
python3 scripts/run_m5_live_smoke.py --json-output examples/m5_live_smoke.json
```

The default smoke checks AAPL, TSLA, and NVDA leverage analysis and verifies that each run succeeds, extracts enough metrics, and includes a `Verified Changes` section in the generated brief.

## What It Shows

- **Control Room:** operating dashboard, enterprise controls, system boundary, and M3 guardrail snapshot.
- **Research Console:** ticker/theme/year workflow, saved M5 smoke results, live generated brief, optional LLM stage workpaper, fact register, and trace.
- **Workpaper Audit:** final M3 brief, trace metrics, and ReAct tool ledger.
- **Model Controls:** numeric guardrail and semantic critic review.
- **System Architecture:** end-to-end flow and LLM/tool boundary.

## Expected Demo Metrics

```json
{
  "final_answer_numeric_guardrail": "pass",
  "phase2_numeric_guardrail": "block",
  "phase2_repaired": true,
  "phase3_fallback_used": false,
  "phase4_numeric_guardrail": "pass",
  "phase4_tool_call_count": 9,
  "phase5_semantic_approved": true
}
```

## Notes

Full live Bedrock ReAct mode is not implemented in this UI. The live SEC module remains deterministic by default; the optional Bedrock mode only adds guarded stage-level analyst workpaper notes after verified facts are extracted.

This demo is for engineering and research presentation only. It is not financial advice.
