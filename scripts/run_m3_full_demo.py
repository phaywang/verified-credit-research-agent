"""Run M3 Phases 2-5 over the existing Ford M2 workpapers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from credit_research_agent.config import RUNS_DIR
from credit_research_agent.m3.artifacts import (
    compact_verified_results,
    load_base_workpapers,
    write_m3_artifact,
)
from credit_research_agent.m3.guardrails import (
    numeric_guardrail_check,
    strip_unverified_financial_lines,
)
from credit_research_agent.m3.query_rewriter import llm_rewrite_query
from credit_research_agent.m3.react_agent import (
    phase4_metrics,
    run_react_agent,
    serialize_tool_loop,
)
from credit_research_agent.m3.semantic_critic import critique_semantics, repair_brief_with_critic
from credit_research_agent.m3.synthesizer import synthesize_credit_brief


RUN_ID = "m3_full_demo"
QUESTION = "How did Ford's debt and liquidity risk change from 2023 to 2025, and what evidence supports the change?"


def _step(
    state: str,
    summary: str,
    *,
    reasoning_summary: str = "",
    decision_basis: List[str] | None = None,
    outputs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "state": state,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "reasoning_summary": reasoning_summary or summary,
        "decision_basis": decision_basis or [],
        "outputs": outputs or {},
    }


def main() -> None:
    workpapers = load_base_workpapers()
    verified = compact_verified_results(workpapers["numeric_verification"])
    steps: List[Dict[str, Any]] = []

    # Phase 2: LLM synthesizer role + deterministic numeric guardrail.
    phase2_brief = synthesize_credit_brief(workpapers)
    phase2_guardrail = numeric_guardrail_check(phase2_brief, verified)
    phase2_final = (
        strip_unverified_financial_lines(phase2_brief, phase2_guardrail)
        if phase2_guardrail["severity"] == "block"
        else phase2_brief
    )
    phase2_repaired = phase2_guardrail["severity"] == "block"
    phase2_final_guardrail = numeric_guardrail_check(phase2_final, verified)
    write_m3_artifact(RUN_ID, "phase2_llm_synthesized_answer.md", phase2_final)
    write_m3_artifact(RUN_ID, "phase2_numeric_guardrail.json", phase2_guardrail)
    steps.append(
        _step(
            "PHASE_2_SYNTHESIZE",
            "LLM synthesizer generated a verified-number-tagged brief; deterministic guardrail evaluated it.",
            reasoning_summary="LLM prose is allowed only after M2 verified facts are supplied as bounded inputs.",
            decision_basis=[f"guardrail_severity={phase2_guardrail['severity']}"],
            outputs={"artifact": str(RUNS_DIR / RUN_ID / "phase2_llm_synthesized_answer.md")},
        )
    )

    # Phase 3: LLM-primary query rewrite.
    rewrite = llm_rewrite_query(
        "Ford debt risk",
        ["missing 2025 management explanation", "missing liquidity evidence"],
        company="Ford",
        years=[2023, 2025],
    )
    write_m3_artifact(RUN_ID, "phase3_query_rewrite.json", rewrite)
    steps.append(
        _step(
            "PHASE_3_QUERY_REWRITE",
            "LLM query rewriter targeted specific evidence gaps.",
            reasoning_summary=rewrite.get("reasoning_summary", ""),
            decision_basis=[
                f"fallback_used={rewrite.get('fallback_used')}",
                f"target_sections={rewrite.get('target_sections')}",
            ],
            outputs=rewrite,
        )
    )

    # Phase 4: ReAct controller with deterministic tools.
    react_result = run_react_agent(QUESTION)
    react_serialized = serialize_tool_loop(react_result)
    write_m3_artifact(RUN_ID, "phase4_react_tool_trace.json", react_serialized)
    phase4_guardrail = numeric_guardrail_check(react_result.final_text, verified)
    phase4_final = (
        strip_unverified_financial_lines(react_result.final_text, phase4_guardrail)
        if phase4_guardrail["severity"] == "block"
        else react_result.final_text
    )
    write_m3_artifact(RUN_ID, "phase4_react_final_answer.md", phase4_final)
    write_m3_artifact(RUN_ID, "phase4_numeric_guardrail.json", phase4_guardrail)
    metrics = phase4_metrics(react_result)
    steps.append(
        _step(
            "PHASE_4_REACT",
            "Bedrock ReAct controller used deterministic tools before finalizing.",
            reasoning_summary="Tool events demonstrate memory, retrieval, numeric verification, and guardrail use.",
            decision_basis=[f"{key}={value}" for key, value in metrics.items()],
            outputs=metrics,
        )
    )

    final_review_text = phase2_final
    write_m3_artifact(RUN_ID, "final_answer.md", final_review_text)

    # Phase 5: LLM semantic critic, after deterministic numeric guardrail.
    critic_report = critique_semantics(final_review_text, workpapers)
    phase5_guardrail = {"severity": "not_run"}
    if not critic_report.get("approved"):
        repaired = repair_brief_with_critic(final_review_text, critic_report, workpapers)
        phase5_guardrail = numeric_guardrail_check(repaired, verified)
        final_review_text = (
            strip_unverified_financial_lines(repaired, phase5_guardrail)
            if phase5_guardrail["severity"] == "block"
            else repaired
        )
        write_m3_artifact(RUN_ID, "final_answer.md", final_review_text)
        write_m3_artifact(RUN_ID, "phase5_repaired_answer.md", final_review_text)
        critic_report = critique_semantics(final_review_text, workpapers)
    write_m3_artifact(RUN_ID, "phase5_semantic_critic.json", critic_report)
    steps.append(
        _step(
            "PHASE_5_DUAL_CRITIC",
            "Dual-layer critic completed: deterministic numeric guardrail plus LLM semantic critic.",
            reasoning_summary=critic_report.get("reasoning_summary", ""),
            decision_basis=[
                f"numeric_guardrail={phase4_guardrail['severity']}",
                f"phase5_repair_guardrail={phase5_guardrail['severity']}",
                f"semantic_approved={critic_report.get('approved')}",
            ],
            outputs=critic_report,
        )
    )

    trace = {
        "run_id": RUN_ID,
        "task": QUESTION,
        "created_at": datetime.now().isoformat(),
        "status": "completed",
        "steps": steps,
        "final_metrics": {
            "phase2_numeric_guardrail": phase2_guardrail["severity"],
            "phase2_repaired": phase2_repaired,
            "final_answer_numeric_guardrail": phase2_final_guardrail["severity"],
            "phase3_fallback_used": rewrite.get("fallback_used"),
            "phase4_tool_call_count": metrics["tool_call_count"],
            "phase4_numeric_guardrail": phase4_guardrail["severity"],
            "phase5_repair_guardrail": phase5_guardrail["severity"],
            "phase5_semantic_approved": critic_report.get("approved"),
        },
        "artifacts": {
            "phase2_answer": str(RUNS_DIR / RUN_ID / "phase2_llm_synthesized_answer.md"),
            "phase3_query_rewrite": str(RUNS_DIR / RUN_ID / "phase3_query_rewrite.json"),
            "phase4_tool_trace": str(RUNS_DIR / RUN_ID / "phase4_react_tool_trace.json"),
            "phase4_answer": str(RUNS_DIR / RUN_ID / "phase4_react_final_answer.md"),
            "final_answer": str(RUNS_DIR / RUN_ID / "final_answer.md"),
            "phase5_critic": str(RUNS_DIR / RUN_ID / "phase5_semantic_critic.json"),
        },
    }
    write_m3_artifact(RUN_ID, "trace_log.json", trace)
    print(json.dumps(trace["final_metrics"], indent=2, sort_keys=True))
    print(f"trace_log={RUNS_DIR / RUN_ID / 'trace_log.json'}")


if __name__ == "__main__":
    main()
