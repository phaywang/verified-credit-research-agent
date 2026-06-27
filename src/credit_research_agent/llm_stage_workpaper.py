"""Optional LLM-written stage workpapers for live credit analysis.

The stage workpaper is deliberately separate from deterministic metric
extraction. It lets an LLM write richer analyst-style narrative while a simple
numeric guardrail prevents unsupported financial numbers from entering the memo.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from credit_research_agent.m3.bedrock_client import invoke_text
from credit_research_agent.sec_integration import MetricValue


InvokeFn = Callable[[str, str, int], str]


@dataclass
class StageWorkpaper:
    """LLM-written analysis for one research stage."""

    stage: str
    status: str
    analysis: str
    guardrail_status: str
    blocked_lines: List[str]
    prompt_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


STAGES = [
    {
        "stage": "1. Intake and Scoping",
        "prompt_summary": "Frame the research request, company, fiscal years, theme, and expected analytical lens.",
    },
    {
        "stage": "2. Fact Verification Review",
        "prompt_summary": "Explain what verified SEC/XBRL facts are available, what is comparable, and what is missing.",
    },
    {
        "stage": "3. Credit Risk Interpretation",
        "prompt_summary": "Translate verified metric movement into credit pressure/support signals without inventing numbers.",
    },
    {
        "stage": "4. Reviewer Questions and Next Work",
        "prompt_summary": "Draft senior-review questions, limitations, and follow-up diligence requests.",
    },
]


SYSTEM_PROMPT = (
    "You are a credit research analyst writing institutional workpaper notes. "
    "Use only the supplied verified SEC/XBRL facts. Do not calculate new numbers. "
    "Do not introduce any financial number that is not present in the supplied facts. "
    "If a point needs missing data, state it as a diligence item instead of inventing it."
)


def generate_stage_workpaper(
    *,
    company: str,
    ticker: str,
    risk_theme: str,
    years: List[int],
    metrics_by_year: Dict[int, List[MetricValue]],
    deterministic_brief: str,
    invoke_fn: Optional[InvokeFn] = None,
) -> List[StageWorkpaper]:
    """Generate guarded LLM stage notes for the live analysis workflow."""

    facts = _compact_metric_facts(metrics_by_year)
    allowed_numbers = _allowed_numbers(years, facts)
    call_llm = invoke_fn or _invoke_bedrock_text
    workpapers: List[StageWorkpaper] = []

    for stage in STAGES:
        prompt = _build_stage_prompt(
            company=company,
            ticker=ticker,
            risk_theme=risk_theme,
            years=years,
            stage=stage["stage"],
            stage_instruction=stage["prompt_summary"],
            facts=facts,
            deterministic_brief=deterministic_brief,
        )

        try:
            raw_analysis = call_llm(prompt, SYSTEM_PROMPT, 1800)
            guarded = _guard_stage_text(raw_analysis, allowed_numbers)
            workpapers.append(
                StageWorkpaper(
                    stage=stage["stage"],
                    status="success" if guarded["status"] == "pass" else "repaired",
                    analysis=guarded["text"],
                    guardrail_status=guarded["status"],
                    blocked_lines=guarded["blocked_lines"],
                    prompt_summary=stage["prompt_summary"],
                )
            )
        except Exception as exc:
            workpapers.append(
                StageWorkpaper(
                    stage=stage["stage"],
                    status="unavailable",
                    analysis=(
                        "LLM stage analysis was not generated. Deterministic brief, "
                        "verified facts, and trace remain available for review."
                    ),
                    guardrail_status="not_run",
                    blocked_lines=[],
                    prompt_summary=f"{stage['prompt_summary']} Error: {exc}",
                )
            )

    return workpapers


def _invoke_bedrock_text(prompt: str, system_prompt: str, max_tokens: int) -> str:
    return invoke_text(
        prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    ).text


def _compact_metric_facts(metrics_by_year: Dict[int, List[MetricValue]]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for year in sorted(metrics_by_year):
        for metric in metrics_by_year[year]:
            facts.append(
                {
                    "metric_name": metric.metric_name,
                    "fiscal_year": metric.fiscal_year,
                    "value": metric.value,
                    "unit": metric.unit,
                    "source": metric.source,
                    "xbrl_concept": metric.xbrl_concept,
                }
            )
    return facts


def _build_stage_prompt(
    *,
    company: str,
    ticker: str,
    risk_theme: str,
    years: List[int],
    stage: str,
    stage_instruction: str,
    facts: List[Dict[str, Any]],
    deterministic_brief: str,
) -> str:
    brief_excerpt = deterministic_brief[:5000]
    return f"""
Write the following workpaper stage for a financial-institution credit research workflow:

Stage: {stage}
Instruction: {stage_instruction}

Company: {company}
Ticker: {ticker}
Risk theme: {risk_theme}
Fiscal years: {', '.join(str(year) for year in years)}

Verified SEC/XBRL facts:
{json.dumps(facts, indent=2, sort_keys=True)}

Deterministic verified brief excerpt:
{brief_excerpt}

Output requirements:
- Use markdown.
- Be detailed enough for senior analyst review.
- Separate observations, credit implications, limitations, and follow-up work where relevant.
- Do not invent facts, ratings, recommendations, forecasts, covenants, or unsupported numbers.
- If you reference a financial number, copy it only from the verified facts above.
- No private chain-of-thought.
"""


def _allowed_numbers(years: Iterable[int], facts: List[Dict[str, Any]]) -> set[str]:
    allowed = {str(year) for year in years}
    for fact in facts:
        value = fact.get("value")
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        allowed.update(
            {
                str(value),
                f"{numeric}",
                f"{numeric:.0f}",
                f"{numeric:.1f}",
                f"{numeric:.2f}",
                f"{numeric:,.0f}",
                f"{numeric:,.1f}",
                f"{numeric:,.2f}",
            }
        )
    return allowed


def _guard_stage_text(text: str, allowed_numbers: set[str]) -> Dict[str, Any]:
    blocked_lines = []
    kept_lines = []

    for line in text.splitlines():
        numbers = _financial_numbers(line)
        unsupported = [
            number for number in numbers
            if number not in allowed_numbers and _normalize_number(number) not in allowed_numbers
        ]
        if unsupported:
            blocked_lines.append(line)
            continue
        kept_lines.append(line)

    status = "pass" if not blocked_lines else "repaired"
    repaired_text = "\n".join(kept_lines).strip()
    if blocked_lines:
        repaired_text += (
            "\n\n_Numeric guardrail note: one or more LLM-written lines were removed "
            "because they contained financial numbers not present in verified facts._"
        )

    return {
        "status": status,
        "text": repaired_text,
        "blocked_lines": blocked_lines,
    }


def _financial_numbers(line: str) -> List[str]:
    numbers = re.findall(r"(?<![A-Za-z])[-+]?\$?\d[\d,]*(?:\.\d+)?%?", line)
    cleaned = []
    for number in numbers:
        stripped = number.strip("$%")
        if _is_metadata_number(stripped):
            continue
        cleaned.append(stripped)
    return cleaned


def _is_metadata_number(number: str) -> bool:
    normalized = number.replace(",", "")
    if not normalized:
        return True
    try:
        value = float(normalized)
    except ValueError:
        return False
    return value.is_integer() and 1900 <= value <= 2100


def _normalize_number(number: str) -> str:
    return number.replace(",", "")
