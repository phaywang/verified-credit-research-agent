# M5 Release Notes: Universal SEC Companyfacts Analysis

M5 upgrades the project from a Ford-focused demo harness into a reusable SEC structured-facts analysis layer. It does not replace the M3 ReAct agent; it adds a deterministic live SEC path for ticker-based numeric credit analysis.

## What Changed

- Added live SEC `companyfacts` integration for structured XBRL facts.
- Fixed SEC request handling with a contact-style `User-Agent`, retry/backoff for transient errors, and correct SEC archive URL construction.
- Corrected SEC `submissions` schema parsing for company name, CIK, ticker, SIC, and annual filing years.
- Added common company XBRL concept mappings for leverage, debt, cash, income, and equity metrics.
- Upgraded generated briefs with deterministic `Verified Changes` tables and analyst notes.
- Added a Streamlit `Live SEC Analysis` tab for ticker/theme/year analysis without Bedrock.
- Added a live smoke script for repeatable multi-company validation.

## Key Capabilities

- Analyze a ticker using SEC APIs:
  - ticker lookup
  - submissions metadata
  - companyfacts JSON
  - configured XBRL concept mapping
  - deterministic metric extraction
  - verified change analysis
- Keep M3's neurosymbolic boundary intact:
  - M3 remains the LLM ReAct + tool-calling harness.
  - M5 live SEC mode is deterministic and does not call Bedrock.
- Produce analyst-readable changes:
  - start/end values
  - absolute changes
  - percentage changes
  - direction
  - metric-level credit interpretation

## Validation Results

Default unit test suite:

```text
Ran 128 tests
OK (skipped=14)
```

M5 live SEC smoke script:

```bash
python3 scripts/run_m5_live_smoke.py --json-output examples/m5_live_smoke.json
```

Smoke result:

```text
status: pass
case_count: 3
failures: []
```

Validated live companies:

| Ticker | Theme | Years | Status | Metrics | Verified Changes |
|---|---|---:|---|---:|---|
| AAPL | leverage_analysis | 2023, 2024 | success | 9 | yes |
| TSLA | leverage_analysis | 2023, 2024 | success | 9 | yes |
| NVDA | leverage_analysis | 2024, 2025 | success | 9 | yes |

The saved smoke artifact is [examples/m5_live_smoke.json](examples/m5_live_smoke.json).

## Streamlit Demo

Run:

```bash
streamlit run streamlit_app.py
```

Modes:

- Static M3 artifact mode: no Bedrock and no SEC network required.
- Live SEC Analysis mode: requires SEC network access, but does not call Bedrock.

## Known Limitations

- The live SEC mode currently emphasizes structured numeric facts. Narrative management explanations still require the filing retrieval and evidence pipeline.
- Metric coverage depends on company and industry. Banks and insurers may need sector-specific mappings before conclusions are strong.
- Derived metrics such as free cash flow and coverage ratios are not fully generalized in M5.
- The live SEC path is deterministic; it is not a full ReAct loop.
- SEC live tests are excluded from default unit tests because sandbox and CI networks may block `sec.gov`.

## Next Roadmap

- Add sector-specific metric packs, especially banks and insurance.
- Add deterministic derived metrics for ratios and free cash flow.
- Connect live SEC numeric facts back into a future ReAct workflow.
- Add narrative 10-K section retrieval for management explanation and risk-factor evidence.
- Expand the MCP server with read-only companyfacts retrieval if needed.

This project remains a research and engineering demo. It is not financial advice.
