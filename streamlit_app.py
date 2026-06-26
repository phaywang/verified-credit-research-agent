"""Static Streamlit demo for the M3 release artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import streamlit as st

from credit_research_agent.universal_analyzer import AnalysisResult, UniversalCreditAnalyzer


ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = ROOT / "examples" / "m3_full_demo"
ARCHITECTURE_FLOW = """User Question
-> Task Spec Parser
-> Memory Reader
-> Skill Loader
-> LLM Planner / ReAct Loop
-> Tool Layer
-> Hybrid Retrieval / Reranking
-> Numeric Verification
-> LLM Synthesizer
-> Numeric Guardrail
-> Dual Critic
-> Workpaper Trace
-> Final Credit Research Brief"""
RISK_THEMES = {
    "Leverage Analysis": "leverage_analysis",
    "Debt & Liquidity": "debt_liquidity",
    "Solvency Assessment": "solvency_assessment",
    "Cash Flow Coverage": "cash_flow_coverage",
}


def read_text(name: str) -> str:
    return (ARTIFACT_DIR / name).read_text(encoding="utf-8")


def read_json(name: str) -> Dict[str, Any]:
    return json.loads((ARTIFACT_DIR / name).read_text(encoding="utf-8"))


def artifact_available() -> bool:
    required = [
        "final_answer.md",
        "trace_log.json",
        "phase4_react_tool_trace.json",
        "final_answer_numeric_guardrail.json",
        "phase5_semantic_critic.json",
    ]
    return all((ARTIFACT_DIR / name).exists() for name in required)


def short_json(value: Any, max_chars: int = 220) -> str:
    text = json.dumps(value, sort_keys=True, default=str)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def tool_events(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        event
        for event in trace.get("events", [])
        if event.get("kind") == "tool_call"
    ]


def render_metric_row(metrics: Dict[str, Any], guardrail: Dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Phase 2 guardrail", str(metrics.get("phase2_numeric_guardrail", "n/a")))
    cols[1].metric("Phase 2 repaired", str(metrics.get("phase2_repaired", "n/a")))
    cols[2].metric("Query rewrite fallback", str(metrics.get("phase3_fallback_used", "n/a")))
    cols[3].metric("Tool calls", str(metrics.get("phase4_tool_call_count", "n/a")))

    cols = st.columns(3)
    cols[0].metric("Final numeric guardrail", str(metrics.get("final_answer_numeric_guardrail", "n/a")))
    cols[1].metric("Blocked claims", str(guardrail.get("blocked_count", "n/a")))
    cols[2].metric("Semantic approved", str(metrics.get("phase5_semantic_approved", "n/a")))


def render_tool_timeline(events: Iterable[Dict[str, Any]]) -> None:
    rows = []
    for index, event in enumerate(events, start=1):
        rows.append(
            {
                "step": index,
                "tool": event.get("tool_name", ""),
                "input": short_json(event.get("tool_input", {}), 160),
                "output": short_json(event.get("tool_result", {}), 220),
                "status": "completed",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def metric_rows(result: AnalysisResult) -> List[Dict[str, Any]]:
    rows = []
    for year, metrics in sorted(result.metrics.items()):
        for metric in metrics:
            rows.append(
                {
                    "fiscal_year": year,
                    "metric": metric.metric_name,
                    "value": metric.value,
                    "unit": metric.unit,
                    "concept": metric.xbrl_concept,
                    "source": metric.source,
                }
            )
    return rows


@st.cache_resource(show_spinner=False)
def get_universal_analyzer() -> UniversalCreditAnalyzer:
    return UniversalCreditAnalyzer()


def render_live_sec_analysis() -> None:
    st.subheader("Live SEC Companyfacts Analysis")
    st.caption(
        "Runs a deterministic SEC companyfacts workflow. This mode does not call Bedrock "
        "and requires network access to sec.gov."
    )

    with st.form("live_sec_analysis_form"):
        cols = st.columns([1, 1, 1])
        ticker = cols[0].text_input("Ticker", value="AAPL").strip().upper()
        theme_label = cols[1].selectbox("Risk theme", list(RISK_THEMES.keys()))
        year_text = cols[2].text_input("Fiscal years", value="2023, 2024")
        submitted = st.form_submit_button("Run Live SEC Analysis", type="primary")

    if not submitted:
        st.info("Enter a US-listed ticker and fiscal years, then run the live SEC analysis.")
        return

    try:
        years = [int(part.strip()) for part in year_text.split(",") if part.strip()]
    except ValueError:
        st.error("Fiscal years must be comma-separated integers, for example: 2023, 2024.")
        return

    if not ticker:
        st.error("Ticker is required.")
        return
    if len(years) < 1:
        st.error("At least one fiscal year is required.")
        return

    analyzer = get_universal_analyzer()
    with st.spinner(f"Fetching SEC companyfacts for {ticker}..."):
        result = analyzer.analyze(ticker, RISK_THEMES[theme_label], years)

    status_type = "success" if result.status == "success" else "warning"
    getattr(st, status_type)(f"Analysis status: {result.status}")
    if result.error:
        st.error(result.error)

    cols = st.columns(4)
    cols[0].metric("Company", result.company or "n/a")
    cols[1].metric("Ticker", result.ticker)
    cols[2].metric("Theme", theme_label)
    cols[3].metric("Metrics", sum(len(items) for items in result.metrics.values()))

    if result.metrics:
        st.subheader("Verified SEC Facts")
        st.dataframe(metric_rows(result), use_container_width=True, hide_index=True)

    if result.brief:
        st.subheader("Generated Credit Brief")
        st.markdown(result.brief)

    with st.expander("Trace"):
        st.json(result.trace)


def main() -> None:
    st.set_page_config(
        page_title="Verified Credit Research Agent",
        page_icon=None,
        layout="wide",
    )

    st.title("Verified Credit Research Agent")
    st.caption(
        "LLM-driven ReAct agent for SEC filing-based credit research, "
        "with deterministic financial verification and auditable traces."
    )

    if not artifact_available():
        st.error(f"Static demo artifacts were not found at {ARTIFACT_DIR}.")
        st.stop()

    final_answer = read_text("final_answer.md")
    trace_log = read_json("trace_log.json")
    tool_trace = read_json("phase4_react_tool_trace.json")
    guardrail = read_json("final_answer_numeric_guardrail.json")
    semantic_critic = read_json("phase5_semantic_critic.json")
    final_metrics = trace_log.get("final_metrics", {})

    overview, live_sec, brief, trace, tools, guardrails, critic, architecture = st.tabs(
        [
            "Overview",
            "Live SEC Analysis",
            "Final Brief",
            "Trace Metrics",
            "Tool Timeline",
            "Guardrail",
            "Semantic Critic",
            "Architecture",
        ]
    )

    with overview:
        st.subheader("Static Demo Artifact Mode")
        st.info("This UI loads committed M3 demo artifacts. It does not call Bedrock or require credentials.")
        if st.button("Load M3 Demo Artifacts", type="primary"):
            st.success("M3 demo artifacts loaded from examples/m3_full_demo/.")

        st.subheader("Milestone Evolution")
        st.markdown(
            """
- **M1:** rule-based retrieval loop over Ford SEC filing chunks.
- **M2:** deterministic numeric verification, memory, skill, and evaluation.
- **M3:** Bedrock ReAct agent with query rewrite, synthesis, dual critic, and numeric guardrails.
"""
        )

        st.subheader("Why this is not a normal RAG bot")
        st.markdown(
            """
The system does more than retrieve passages and ask an LLM to summarize them. M3 uses an LLM-driven ReAct loop with Bedrock tool calling, deterministic numeric verification, guardrail repair, dual critic review, and auditable workpaper traces. Financial numbers survive into the final brief only when they are tied to verified facts or cited filing evidence.
"""
        )

        render_metric_row(final_metrics, guardrail)

    with live_sec:
        render_live_sec_analysis()

    with brief:
        st.markdown(final_answer)

    with trace:
        st.subheader("M3 Trace Metrics")
        render_metric_row(final_metrics, guardrail)
        with st.expander("Trace JSON"):
            st.json(trace_log)

    with tools:
        st.subheader("Phase 4 ReAct Tool Call Timeline")
        st.caption(f"Tool call count: {tool_trace.get('tool_call_count', 'n/a')}")
        render_tool_timeline(tool_events(tool_trace))
        with st.expander("Raw tool trace JSON"):
            st.json(tool_trace)

    with guardrails:
        st.subheader("Numeric Guardrail Result")
        cols = st.columns(3)
        cols[0].metric("Severity", str(guardrail.get("severity", "n/a")))
        cols[1].metric("Blocked claims", str(guardrail.get("blocked_count", "n/a")))
        cols[2].metric("Financial numbers checked", str(guardrail.get("financial_numbers_checked", "n/a")))
        st.write(guardrail.get("reasoning_summary", ""))
        with st.expander("Guardrail JSON"):
            st.json(guardrail)

    with critic:
        st.subheader("Semantic Critic Result")
        st.metric("Approved", str(semantic_critic.get("approved", "n/a")))
        st.write(semantic_critic.get("reasoning_summary", ""))
        st.markdown("**Review notes**")
        for issue in semantic_critic.get("issues", []):
            st.write(f"- {issue}")
        with st.expander("Semantic critic JSON"):
            st.json(semantic_critic)

    with architecture:
        st.subheader("Architecture Flow")
        st.code(ARCHITECTURE_FLOW, language="text")
        st.caption("M4 is a presentation layer over the frozen M3 release artifacts.")


if __name__ == "__main__":
    main()
