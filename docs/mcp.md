# M4 Minimal MCP Server

M4.3 adds a real, minimal MCP server as a post-M3 integration layer.

The server exposes selected deterministic M3 tools. It does not expose the LLM synthesizer, semantic critic, full ReAct loop, or live Bedrock demo runner.

## Scope

The first MCP version is read-only and Ford-only:

- `hybrid_retrieve`
- `verify_numeric_claim`

Current limitation: only `ticker = "F"` is supported.

## Start the Server

```bash
python3 -m credit_research_agent.mcp.server
```

The server uses the Python MCP SDK and defaults to stdio transport through `FastMCP`.

## Tool: hybrid_retrieve

Purpose: search Ford SEC filing evidence through the existing M3 hybrid retrieval pipeline.

Input:

```json
{
  "query": "Ford 2025 debt liquidity credit facilities",
  "top_n": 10,
  "filters": {
    "ticker": "F",
    "years": [2023, 2025],
    "sections": ["Liquidity and Capital Resources", "Debt"]
  }
}
```

`filters` is optional. M4.3 accepts `ticker`, `years`, and `sections`; only Ford ticker `F` is supported.

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
  ],
  "supported_ticker": "F",
  "note": "M4.3 MCP retrieval is read-only and currently supports Ford ticker F."
}
```

The MCP layer bounds text previews to avoid giant payloads and does not write artifacts.

## Tool: verify_numeric_claim

Purpose: verify a Ford debt/liquidity metric using the existing deterministic M3 verification code path.

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
  ],
  "supported_ticker": "F",
  "note": "M4.3 MCP verification is read-only and currently supports Ford ticker F."
}
```

The MCP layer does not recompute values. It delegates verification to the existing M3 deterministic wrapper.

## Test

```bash
python3 -m unittest tests/test_mcp_server.py
python3 -m unittest discover tests
```

## Boundary

MCP is a post-M3 integration layer. It wraps completed M3 deterministic capabilities and does not change:

- M3 ReAct behavior.
- numeric verification logic.
- guardrail logic.
- final answer generation.

