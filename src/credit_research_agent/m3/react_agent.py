"""M3 Phase 4 ReAct-style loop using deterministic tools."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from credit_research_agent.m3.bedrock_client import ToolLoopResult, invoke_with_tools
from credit_research_agent.m3.tool_specs import ford_research_registry


SYSTEM_PROMPT = (
    "You are the LLM ReAct controller for a verified credit research agent. "
    "Use only the deterministic tools provided for retrieval, memory, calculations, "
    "numeric verification, numeric guardrails, and workpaper writing. "
    "The synthesizer and critic are LLM roles, not tools. "
    "Never invent or calculate financial numbers yourself. "
    "Do not expose private chain-of-thought; final answers may include concise rationale."
)


def run_react_agent(question: str) -> ToolLoopResult:
    prompt = f"""
Answer this credit research question:
{question}

Minimum required tool behavior before final answer:
1. Call query_memory for debt_liquidity.
2. Call hybrid_retrieve with top_n=4 and a query targeting Ford 2023/2025 debt, liquidity, MD&A, and credit facilities.
3. Verify these five metrics with verify_numeric_claim:
   - company_debt_excluding_ford_credit
   - company_debt_payable_within_one_year
   - company_long_term_debt_payable_after_one_year
   - total_balance_sheet_cash_and_marketable_securities_restricted_cash
   - company_liquidity
4. Draft a concise answer under 250 words. Every financial number must be same-line tagged with [verified: claim_id].
5. Call numeric_guardrail_check on the draft before finalizing.
6. If the guardrail blocks, remove or rewrite the blocked financial-number line.
7. Do not use markdown tables, approximate numbers, arrows, or emojis in the final answer.

Final answer sections:
- Executive summary
- Debt risk changes
- Liquidity risk changes
- Evidence and limitations
"""
    return invoke_with_tools(
        prompt,
        ford_research_registry(),
        system_prompt=SYSTEM_PROMPT,
        max_turns=11,
        max_tokens=1400,
    )


def serialize_tool_loop(result: ToolLoopResult) -> Dict[str, Any]:
    return {
        "final_text": result.final_text,
        "stop_reason": result.stop_reason,
        "events": [asdict(event) for event in result.events],
        "tool_call_count": len([event for event in result.events if event.kind == "tool_call"]),
        "tools_called": [
            event.tool_name for event in result.events if event.kind == "tool_call"
        ],
    }


def phase4_metrics(result: ToolLoopResult) -> Dict[str, Any]:
    tools: List[str] = [
        str(event.tool_name) for event in result.events if event.kind == "tool_call"
    ]
    return {
        "tool_call_count": len(tools),
        "used_query_memory": "query_memory" in tools,
        "used_hybrid_retrieve": "hybrid_retrieve" in tools,
        "used_numeric_verifier": "verify_numeric_claim" in tools,
        "used_numeric_guardrail": "numeric_guardrail_check" in tools,
        "stop_reason": result.stop_reason,
    }
