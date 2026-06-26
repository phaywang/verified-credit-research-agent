"""LLM synthesizer role for M3 Phase 2."""

from __future__ import annotations

import json
from typing import Any, Dict

from credit_research_agent.m3.artifacts import compact_evidence, compact_verified_results
from credit_research_agent.m3.bedrock_client import invoke_text


SYSTEM_PROMPT = (
    "You are the LLM synthesizer role for a verified credit research agent. "
    "You may write concise analysis, but every financial number must be copied from "
    "the verified numeric results and include the same-line tag [verified: claim_id]. "
    "Do not invent or calculate numbers. Do not expose private chain-of-thought."
)


def synthesize_credit_brief(workpapers: Dict[str, Any]) -> str:
    verified = compact_verified_results(workpapers["numeric_verification"])
    evidence = compact_evidence(workpapers["evidence_table"], limit=8)
    prompt = f"""
Write a concise Ford debt/liquidity credit research brief for:
"How did Ford's debt and liquidity risk change from 2023 to 2025, and what evidence supports the change?"

Required sections:
1. Executive summary
2. Debt risk changes
3. Liquidity risk changes
4. Management explanation
5. Evidence and limitations

Credit logic required:
- Distinguish Company excluding Ford Credit from Ford Credit and total balance sheet cash.
- Explain that long-term debt after one year declined while debt payable within one year increased.
- Do not say liquidity simply improved or deteriorated when metrics point in different directions.
- Every financial number must have same-line [verified: claim_id].
- Use chunk ids for citations where available.
- Do not use markdown tables for numeric metrics; use bullets/sentences so the verified tag stays on the same line.
- Do not discuss Ford Credit total debt unless a verified result is provided for that exact metric.

Verified numeric results:
{json.dumps(verified, indent=2)}

Evidence excerpts:
{json.dumps(evidence, indent=2)}
"""
    return invoke_text(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=2400).text
