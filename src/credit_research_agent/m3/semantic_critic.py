"""LLM semantic critic role for M3 Phase 5."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from credit_research_agent.m3.artifacts import compact_evidence, compact_verified_results
from credit_research_agent.m3.bedrock_client import invoke_text


def critique_semantics(brief_text: str, workpapers: Dict[str, Any]) -> Dict[str, Any]:
    prompt = _critic_prompt(brief_text, workpapers, compact=False)
    result = invoke_text(
        prompt,
        system_prompt=(
            "You are the LLM semantic critic role. Return compact JSON only. "
            "No markdown. No quoted passages. No private chain-of-thought."
        ),
        max_tokens=900,
    )
    try:
        return parse_rewrite_json_critic(result.text)
    except Exception:
        retry_prompt = _critic_prompt(brief_text[:3500], workpapers, compact=True)
        retry = invoke_text(
            retry_prompt,
            system_prompt=(
                "Return one valid compact JSON object only. "
                "Use short strings. No markdown. No quoted passages."
            ),
            max_tokens=500,
        )
        try:
            return parse_rewrite_json_critic(retry.text)
        except Exception as exc:
            return {
                "approved": False,
                "reasoning_summary": "Semantic critic response was not valid JSON after retry.",
                "issues": [str(exc)],
                "repair_suggestions": ["Review the final brief manually."],
            }


def repair_brief_with_critic(
    brief_text: str,
    critic_report: Dict[str, Any],
    workpapers: Dict[str, Any],
) -> str:
    """LLM repair role for Phase 5, bounded by verified facts."""

    prompt = f"""
Repair the Ford debt/liquidity brief using the critic report.

Rules:
- Preserve only verified financial numbers and same-line [verified: claim_id] tags.
- Do not add financial numbers not present in verified results.
- Do not use markdown numeric tables.
- Keep the answer concise but complete.
- If making a credit interpretation, qualify it as based on maturity mix/liquidity evidence only.

Critic report:
{json.dumps(critic_report, indent=2)}

Verified numeric results:
{json.dumps(compact_verified_results(workpapers["numeric_verification"]), indent=2)}

Original brief:
{brief_text}
"""
    return invoke_text(
        prompt,
        system_prompt=(
            "You are the LLM repair role for a verified credit research agent. "
            "Return only the repaired brief. No private chain-of-thought."
        ),
        max_tokens=2200,
    ).text


def _critic_prompt(brief_text: str, workpapers: Dict[str, Any], *, compact: bool) -> str:
    evidence_limit = 4 if compact else 6
    result_limit = 5 if compact else 10
    verified = compact_verified_results(workpapers["numeric_verification"])[:result_limit]
    evidence = compact_evidence(workpapers["evidence_table"], limit=evidence_limit)
    return f"""
Evaluate this Ford debt/liquidity brief as a semantic critic.

Return JSON only with:
- approved: boolean
- reasoning_summary: short audit summary, no private chain-of-thought
- issues: array of max 3 short strings
- repair_suggestions: array of max 3 short strings

Check:
1. No unsupported financial conclusion beyond verified facts.
2. Debt maturity mix is explained correctly.
3. Liquidity conclusion is scoped and not overgeneralized.
4. Citations/chunk ids are used where evidence is referenced.
Approve if the brief is materially supportable and limitations disclose missing refinancing/covenant/cash-flow details.
Do not require every verified metric to be included if the answer is otherwise scoped and accurate.

Verified numeric results:
{json.dumps(verified, indent=2)}

Evidence excerpts:
{json.dumps(evidence, indent=2)}

Brief:
{brief_text}
"""


def parse_rewrite_json_critic(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in critic response.")
        cleaned = match.group(0)
    parsed = json.loads(cleaned)
    required = {"approved", "reasoning_summary", "issues", "repair_suggestions"}
    missing = required - set(parsed)
    if missing:
        raise ValueError(f"Critic JSON missing fields: {sorted(missing)}")
    return parsed
