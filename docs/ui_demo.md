# M4 Static Demo UI

The M4 static demo UI presents the completed M3 release artifacts without requiring Bedrock credentials.

## Run

```bash
streamlit run streamlit_app.py
```

## Mode

The first M4 UI mode is static artifact mode. It loads committed files from:

```text
examples/m3_full_demo/
```

It does not call Bedrock, run the M3 pipeline, or require API credentials.

## What It Shows

- Project overview and milestone evolution.
- Why the system is not a normal RAG bot.
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

Live Bedrock mode is not implemented in M4.2. It remains future M4.4 work.

This demo is for engineering and research presentation only. It is not financial advice.
