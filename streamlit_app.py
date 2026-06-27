"""Streamlit demo UI for the Verified Credit Research Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import streamlit as st

from credit_research_agent.universal_analyzer import AnalysisResult, UniversalCreditAnalyzer


ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = ROOT / "examples" / "m3_full_demo"
M5_SMOKE_PATH = ROOT / "examples" / "m5_live_smoke.json"

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

LIVE_SAMPLE_CASES = {
    "Apple leverage: AAPL 2023-2024": ("AAPL", "Leverage Analysis", "2023, 2024"),
    "Tesla leverage: TSLA 2023-2024": ("TSLA", "Leverage Analysis", "2023, 2024"),
    "NVIDIA leverage: NVDA 2024-2025": ("NVDA", "Leverage Analysis", "2024, 2025"),
    "Custom": ("AAPL", "Leverage Analysis", "2023, 2024"),
}


def inject_css() -> None:
    """Apply restrained product styling."""
    st.markdown(
        """
<style>
  :root {
    --ink: #1f2430;
    --muted: #667085;
    --line: #e5e7eb;
    --soft: #f6f8fb;
    --panel: #ffffff;
    --accent: #bf2f45;
    --accent-soft: #fff1f3;
    --good: #0f766e;
    --warn: #b45309;
  }
  .block-container {
    padding-top: 2.4rem;
    max-width: 1320px;
  }
  div[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
    position: fixed;
  }
  h1, h2, h3 {
    letter-spacing: 0;
  }
  .hero {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 26px 28px;
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    margin-bottom: 18px;
  }
  .eyebrow {
    color: var(--accent);
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
  }
  .hero h1 {
    margin: 0 0 8px 0;
    color: var(--ink);
    font-size: 2.35rem;
    line-height: 1.08;
  }
  .hero p {
    color: var(--muted);
    max-width: 920px;
    margin-bottom: 16px;
  }
  .badge-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .badge {
    border: 1px solid var(--line);
    background: #ffffff;
    border-radius: 999px;
    padding: 5px 10px;
    color: #344054;
    font-size: 0.78rem;
    font-weight: 600;
  }
  .status-card {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 8px;
    padding: 16px 16px 14px;
    min-height: 112px;
  }
  .status-card .label {
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .status-card .value {
    color: var(--ink);
    font-size: 1.55rem;
    font-weight: 760;
    line-height: 1.15;
    overflow-wrap: anywhere;
  }
  .status-card .note {
    color: var(--muted);
    font-size: 0.82rem;
    margin-top: 8px;
  }
  .panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    padding: 18px;
    margin-bottom: 16px;
  }
  .panel h3 {
    margin-top: 0;
  }
  .section-kicker {
    color: var(--accent);
    font-size: 0.78rem;
    text-transform: uppercase;
    font-weight: 750;
    margin-bottom: 4px;
  }
  .callout {
    border-left: 4px solid var(--accent);
    background: var(--accent-soft);
    padding: 13px 15px;
    border-radius: 6px;
    color: #5c1f2a;
  }
  .small-muted {
    color: var(--muted);
    font-size: 0.86rem;
  }
  .workflow-step {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 12px;
    background: #ffffff;
    min-height: 88px;
  }
  .workflow-step strong {
    display: block;
    color: var(--ink);
    margin-bottom: 4px;
  }
  div[data-testid="stMetric"] {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 12px 14px;
    background: #ffffff;
  }
  div[data-testid="stMetricLabel"] p {
    color: var(--muted);
    font-weight: 650;
  }
  .stTabs [data-baseweb="tab-list"] {
    gap: 14px;
    border-bottom: 1px solid var(--line);
  }
  .stTabs [data-baseweb="tab"] {
    padding-left: 0;
    padding-right: 0;
  }
  .stDataFrame {
    border: 1px solid var(--line);
    border-radius: 8px;
  }
</style>
""",
        unsafe_allow_html=True,
    )


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


def status_card(label: str, value: Any, note: str = "") -> None:
    st.markdown(
        f"""
<div class="status-card">
  <div class="label">{label}</div>
  <div class="value">{value}</div>
  <div class="note">{note}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
<div class="hero">
  <div class="eyebrow">Verified Credit Research Agent</div>
  <h1>Auditable SEC credit research with LLM reasoning and deterministic controls</h1>
  <p>
    A portfolio-grade credit research harness combining agentic retrieval,
    Bedrock ReAct tool calling, SEC companyfacts analysis, numeric guardrails,
    and workpaper-style traces.
  </p>
  <div class="badge-row">
    <span class="badge">M3 ReAct agent</span>
    <span class="badge">M5 live SEC companyfacts</span>
    <span class="badge">Deterministic numeric verification</span>
    <span class="badge">Auditable workpapers</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_metric_row(metrics: Dict[str, Any], guardrail: Dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Phase 2 guardrail", str(metrics.get("phase2_numeric_guardrail", "n/a")))
    cols[1].metric("Phase 2 repaired", str(metrics.get("phase2_repaired", "n/a")))
    cols[2].metric("LLM rewrite fallback", str(metrics.get("phase3_fallback_used", "n/a")))
    cols[3].metric("ReAct tool calls", str(metrics.get("phase4_tool_call_count", "n/a")))

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


def metric_map(result: AnalysisResult, year: int) -> Dict[str, Any]:
    return {
        metric.metric_name: metric
        for metric in result.metrics.get(year, [])
        if metric.value is not None
    }


def change_rows(result: AnalysisResult) -> List[Dict[str, Any]]:
    if len(result.years) < 2:
        return []

    start_year = min(result.years)
    end_year = max(result.years)
    start = metric_map(result, start_year)
    end = metric_map(result, end_year)
    rows = []

    for name in sorted(set(start) & set(end)):
        old = start[name]
        new = end[name]
        absolute = new.value - old.value
        percent: Optional[float] = None
        if old.value:
            percent = absolute / abs(old.value) * 100
        rows.append(
            {
                "metric": name,
                "start_year": start_year,
                "start_value": round(old.value, 2),
                "end_year": end_year,
                "end_value": round(new.value, 2),
                "absolute_change": round(absolute, 2),
                "percent_change": None if percent is None else round(percent, 2),
                "direction": "increased" if absolute > 0 else "decreased" if absolute < 0 else "unchanged",
            }
        )
    return rows


@st.cache_resource(show_spinner=False)
def get_universal_analyzer() -> UniversalCreditAnalyzer:
    return UniversalCreditAnalyzer()


def parse_years(year_text: str) -> List[int]:
    return [int(part.strip()) for part in year_text.split(",") if part.strip()]


def render_live_sec_analysis() -> None:
    st.markdown('<div class="section-kicker">Live deterministic mode</div>', unsafe_allow_html=True)
    st.subheader("SEC companyfacts analysis")
    st.markdown(
        """
<div class="callout">
  This workflow uses SEC structured companyfacts for verified numeric facts.
  It does not call Bedrock, and it does not rely on local filing fixtures.
</div>
""",
        unsafe_allow_html=True,
    )

    form_col, guide_col = st.columns([1.1, 0.9], gap="large")

    with form_col:
        with st.container(border=True):
            sample_label = st.selectbox("Sample case", list(LIVE_SAMPLE_CASES.keys()))
            sample_ticker, sample_theme, sample_years = LIVE_SAMPLE_CASES[sample_label]
            with st.form("live_sec_analysis_form"):
                cols = st.columns([0.8, 1.2, 1])
                ticker = cols[0].text_input("Ticker", value=sample_ticker).strip().upper()
                theme_label = cols[1].selectbox(
                    "Risk theme",
                    list(RISK_THEMES.keys()),
                    index=list(RISK_THEMES.keys()).index(sample_theme),
                )
                year_text = cols[2].text_input("Fiscal years", value=sample_years)
                submitted = st.form_submit_button("Run live SEC analysis", type="primary", use_container_width=True)

    with guide_col:
        st.markdown(
            """
<div class="panel">
  <h3>What this proves</h3>
  <p class="small-muted">
    The app can retrieve fresh SEC structured facts, map XBRL concepts by metric,
    calculate verified changes, and generate a concise credit brief without
    allowing the LLM to invent numbers.
  </p>
  <div class="badge-row">
    <span class="badge">ticker lookup</span>
    <span class="badge">companyfacts</span>
    <span class="badge">verified changes</span>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    if not submitted:
        render_m5_smoke_summary()
        return

    try:
        years = parse_years(year_text)
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

    render_live_result(result, theme_label)


def render_live_result(result: AnalysisResult, theme_label: str) -> None:
    total_metrics = sum(len(items) for items in result.metrics.values())
    status_note = "Ready for analyst review" if result.status == "success" else result.error or "Review trace"

    st.divider()
    cols = st.columns(4)
    with cols[0]:
        status_card("Company", result.company or "n/a", result.ticker)
    with cols[1]:
        status_card("Status", result.status, status_note)
    with cols[2]:
        status_card("Verified facts", total_metrics, "SEC companyfacts metrics")
    with cols[3]:
        status_card("Theme", theme_label, ", ".join(str(year) for year in result.years))

    if result.error:
        st.error(result.error)

    changes = change_rows(result)
    if changes:
        st.subheader("Verified Changes")
        st.dataframe(changes, use_container_width=True, hide_index=True)

    result_tabs = st.tabs(["Credit Brief", "Verified Facts", "Trace"])
    with result_tabs[0]:
        if result.brief:
            st.markdown(result.brief)
        else:
            st.warning("No brief was generated.")
    with result_tabs[1]:
        rows = metric_rows(result)
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No metrics were extracted for the selected years/theme.")
    with result_tabs[2]:
        st.json(result.trace)


def render_m5_smoke_summary() -> None:
    st.subheader("Latest M5 live smoke")
    if not M5_SMOKE_PATH.exists():
        st.info("No saved M5 smoke artifact found yet.")
        return

    smoke = json.loads(M5_SMOKE_PATH.read_text(encoding="utf-8"))
    cols = st.columns(3)
    cols[0].metric("Smoke status", smoke.get("status", "n/a"))
    cols[1].metric("Cases", str(smoke.get("case_count", "n/a")))
    cols[2].metric("Failures", str(len(smoke.get("failures", []))))

    rows = [
        {
            "ticker": item.get("ticker"),
            "company": item.get("company"),
            "theme": item.get("theme"),
            "status": item.get("status"),
            "metrics": item.get("total_metrics"),
            "verified_changes": item.get("has_verified_changes"),
        }
        for item in smoke.get("summaries", [])
    ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_overview(final_metrics: Dict[str, Any], guardrail: Dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Portfolio project status</div>', unsafe_allow_html=True)
    st.subheader("Narrow, complete, auditable credit research agent")

    cols = st.columns(4)
    with cols[0]:
        status_card("Milestones", "M1-M5", "retrieval, verification, ReAct, UI, SEC")
    with cols[1]:
        status_card("M3 ReAct calls", final_metrics.get("phase4_tool_call_count", "n/a"), "real Bedrock demo")
    with cols[2]:
        status_card("Final guardrail", final_metrics.get("final_answer_numeric_guardrail", "n/a"), "unsupported numbers blocked")
    with cols[3]:
        status_card("M5 smoke", "pass", "AAPL, TSLA, NVDA")

    st.markdown("### Why this is not a normal RAG bot")
    st.markdown(
        """
The system does more than retrieve passages and summarize them. It plans a credit
research workflow, retrieves SEC evidence, rewrites weak queries, verifies numeric
claims with deterministic tools, blocks unsupported financial numbers, records a
workpaper trace, and now adds a live SEC companyfacts path for reusable ticker
analysis.
"""
    )

    st.markdown("### Milestone map")
    steps = st.columns(5)
    milestone_text = [
        ("M1", "Agentic retrieval loop", "hybrid search, rerank, rewrite"),
        ("M2", "Numeric verification", "XBRL-first debt facts, critic"),
        ("M3", "LLM ReAct agent", "Bedrock tools and guardrails"),
        ("M4", "Demo and MCP", "Streamlit and read-only tools"),
        ("M5", "Live SEC facts", "universal companyfacts analysis"),
    ]
    for column, (title, headline, detail) in zip(steps, milestone_text):
        with column:
            st.markdown(
                f"""
<div class="workflow-step">
  <strong>{title}: {headline}</strong>
  <span class="small-muted">{detail}</span>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("### M3 guardrail snapshot")
    render_metric_row(final_metrics, guardrail)


def render_workpaper(final_answer: str, trace_log: Dict[str, Any], tool_trace: Dict[str, Any]) -> None:
    brief_tab, trace_tab, tools_tab = st.tabs(["Final Brief", "Trace Metrics", "Tool Timeline"])
    with brief_tab:
        st.markdown(final_answer)
    with trace_tab:
        st.subheader("M3 workpaper trace")
        final_metrics = trace_log.get("final_metrics", {})
        cols = st.columns(4)
        cols[0].metric("Loop phase", "M3")
        cols[1].metric("Tool calls", str(final_metrics.get("phase4_tool_call_count", "n/a")))
        cols[2].metric("Repair run", str(final_metrics.get("phase2_repaired", "n/a")))
        cols[3].metric("Semantic approved", str(final_metrics.get("phase5_semantic_approved", "n/a")))
        with st.expander("Trace JSON"):
            st.json(trace_log)
    with tools_tab:
        st.subheader("Phase 4 ReAct tool timeline")
        st.caption(f"Tool call count: {tool_trace.get('tool_call_count', 'n/a')}")
        render_tool_timeline(tool_events(tool_trace))
        with st.expander("Raw tool trace JSON"):
            st.json(tool_trace)


def render_guardrails(guardrail: Dict[str, Any], semantic_critic: Dict[str, Any]) -> None:
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Numeric guardrail")
        cols = st.columns(3)
        cols[0].metric("Severity", str(guardrail.get("severity", "n/a")))
        cols[1].metric("Blocked claims", str(guardrail.get("blocked_count", "n/a")))
        cols[2].metric("Numbers checked", str(guardrail.get("financial_numbers_checked", "n/a")))
        st.write(guardrail.get("reasoning_summary", ""))
        with st.expander("Guardrail JSON"):
            st.json(guardrail)
    with right:
        st.subheader("Semantic critic")
        st.metric("Approved", str(semantic_critic.get("approved", "n/a")))
        st.write(semantic_critic.get("reasoning_summary", ""))
        issues = semantic_critic.get("issues", [])
        if issues:
            for issue in issues:
                st.write(f"- {issue}")
        else:
            st.write("No semantic critic issues reported.")
        with st.expander("Semantic critic JSON"):
            st.json(semantic_critic)


def render_architecture() -> None:
    st.subheader("Architecture flow")
    st.code(ARCHITECTURE_FLOW, language="text")
    st.markdown(
        """
**Boundary:** the LLM handles planning, query rewrite, synthesis, and semantic
critique. Deterministic Python tools handle retrieval execution, calculations,
numeric verification, guardrails, and workpaper persistence.

**M5 addition:** live SEC companyfacts analysis adds a structured numeric path
for reusable ticker demos. It complements, rather than replaces, the M3 ReAct
agent.
"""
    )


def main() -> None:
    st.set_page_config(
        page_title="Verified Credit Research Agent",
        page_icon=None,
        layout="wide",
    )
    inject_css()
    render_hero()

    if not artifact_available():
        st.error(f"Static demo artifacts were not found at {ARTIFACT_DIR}.")
        st.stop()

    final_answer = read_text("final_answer.md")
    trace_log = read_json("trace_log.json")
    tool_trace = read_json("phase4_react_tool_trace.json")
    guardrail = read_json("final_answer_numeric_guardrail.json")
    semantic_critic = read_json("phase5_semantic_critic.json")
    final_metrics = trace_log.get("final_metrics", {})

    overview, live_sec, workpaper, guardrails, architecture = st.tabs(
        [
            "Overview",
            "Live SEC Analysis",
            "M3 Workpaper",
            "Guardrails & Critic",
            "Architecture",
        ]
    )

    with overview:
        render_overview(final_metrics, guardrail)
    with live_sec:
        render_live_sec_analysis()
    with workpaper:
        render_workpaper(final_answer, trace_log, tool_trace)
    with guardrails:
        render_guardrails(guardrail, semantic_critic)
    with architecture:
        render_architecture()


if __name__ == "__main__":
    main()
