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

## Live SEC Analysis Mode

The **Live SEC Analysis** tab accepts:

- ticker, such as `AAPL`
- risk theme, such as `Leverage Analysis`
- fiscal years, such as `2023, 2024`

It then runs the deterministic universal analyzer:

```text
ticker lookup
-> SEC submissions metadata
-> SEC companyfacts JSON
-> configured XBRL concept mapping
-> verified metric extraction
-> deterministic credit brief
```

This mode does not call Bedrock. It requires live access to `www.sec.gov` and `data.sec.gov`.

## What It Shows

- Project overview and milestone evolution.
- Why the system is not a normal RAG bot.
- Live SEC companyfacts analysis, when network access is available.
- Final M3 credit research brief.
- Trace metrics.
- Phase 4 ReAct tool call timeline.
- Numeric guardrail result.
- Semantic critic result.
- Architecture flow.

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

Live Bedrock mode is not implemented in this UI. The live SEC tab is deterministic and uses SEC structured facts rather than the M3 Bedrock ReAct loop.

This demo is for engineering and research presentation only. It is not financial advice.
