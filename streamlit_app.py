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
    """Apply restrained enterprise product styling."""
    st.markdown(
        """
<style>
  :root {
    --ink: #111827;
    --muted: #667085;
    --line: #d9dee7;
    --soft: #f7f8fa;
    --soft-2: #eef2f6;
    --panel: #ffffff;
    --accent: #8f1d2f;
    --accent-soft: #fff3f5;
    --good: #0f766e;
    --warn: #a15c07;
    --bad: #b42318;
  }
  .stApp {
    background: #f3f5f8;
  }
  .block-container {
    padding-top: 1.45rem;
    padding-bottom: 3rem;
    max-width: 1440px;
  }
  header[data-testid="stHeader"] {
    background: transparent;
    height: 0;
    min-height: 0;
    pointer-events: none;
  }
  header[data-testid="stHeader"] > div {
    height: 0;
    min-height: 0;
  }
  div[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
    position: fixed;
  }
  section[data-testid="stSidebar"] {
    background: #0f172a;
    border-right: 1px solid #1f2937;
  }
  section[data-testid="stSidebar"] * {
    color: #e5e7eb;
  }
  section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {
    color: #cbd5e1;
    font-size: 0.86rem;
  }
  section[data-testid="stSidebar"] hr {
    border-color: #374151;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label {
    background: #172033;
    border: 1px solid #293548;
    border-radius: 7px;
    padding: 8px 9px;
    margin-bottom: 7px;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: #22304a;
    border-color: #475569;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label p {
    color: #f8fafc;
    font-weight: 650;
    font-size: 0.88rem;
  }
  h1, h2, h3 {
    letter-spacing: 0;
  }
  h1 {
    font-size: 1.72rem;
  }
  h2 {
    font-size: 1.28rem;
  }
  h3 {
    font-size: 1.03rem;
  }
  .topbar {
    border: 1px solid var(--line);
    border-top: 3px solid var(--accent);
    border-radius: 8px;
    background: #ffffff;
    padding: 14px 16px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  }
  .topbar-title {
    display: flex;
    gap: 11px;
    align-items: flex-start;
  }
  .brandmark {
    width: 34px;
    height: 34px;
    border-radius: 7px;
    background: #111827;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.04em;
  }
  .product-label {
    color: #475467;
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
  }
  .topbar h1 {
    margin: 0 0 8px 0;
    color: var(--ink);
    font-size: 1.62rem;
    line-height: 1.2;
  }
  .topbar p {
    color: var(--muted);
    margin: 0;
    font-size: 0.9rem;
  }
  .badge-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .badge {
    border: 1px solid var(--line);
    background: #ffffff;
    border-radius: 6px;
    padding: 4px 8px;
    color: #344054;
    font-size: 0.74rem;
    font-weight: 600;
    white-space: nowrap;
  }
  .badge.good {
    color: var(--good);
    border-color: #99d5cc;
    background: #ecfdf9;
  }
  .badge.warn {
    color: var(--warn);
    border-color: #f4c790;
    background: #fffbeb;
  }
  .badge.dark {
    color: #dbeafe;
    border-color: #334155;
    background: #1f2937;
  }
  .command-strip {
    border: 1px solid var(--line);
    background: #ffffff;
    border-radius: 8px;
    padding: 9px 12px;
    margin-bottom: 14px;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  }
  .command-strip .left,
  .command-strip .right {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
  }
  .command-label {
    color: #475467;
    font-size: 0.75rem;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .control-chip {
    border: 1px solid #d9dee7;
    background: #f8fafc;
    color: #344054;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 0.75rem;
    font-weight: 650;
  }
  .control-chip.ok {
    color: var(--good);
    background: #ecfdf9;
    border-color: #9bd6cc;
  }
  .status-card {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 8px;
    padding: 12px 13px 11px;
    min-height: 88px;
  }
  .status-card .label {
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .status-card .value {
    color: var(--ink);
    font-size: 1.28rem;
    font-weight: 760;
    line-height: 1.15;
    overflow-wrap: anywhere;
  }
  .status-card .note {
    color: var(--muted);
    font-size: 0.78rem;
    margin-top: 6px;
  }
  .panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    padding: 15px;
    margin-bottom: 16px;
  }
  .panel h3 {
    margin-top: 0;
  }
  .section-kicker {
    color: #475467;
    font-size: 0.72rem;
    text-transform: uppercase;
    font-weight: 750;
    margin-bottom: 3px;
    letter-spacing: 0.08em;
  }
  .callout {
    border-left: 3px solid var(--accent);
    background: #ffffff;
    border-top: 1px solid var(--line);
    border-right: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    padding: 11px 13px;
    border-radius: 6px;
    color: #344054;
  }
.small-muted {
    color: var(--muted);
    font-size: 0.86rem;
  }
  .module-header {
    border: 1px solid var(--line);
    background: #ffffff;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 14px;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  }
  .module-header strong {
    color: var(--ink);
    display: block;
    margin-bottom: 2px;
  }
  .module-header span {
    color: var(--muted);
    font-size: 0.84rem;
  }
  .module-code {
    color: #475467;
    background: #f8fafc;
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 0.72rem;
    font-weight: 750;
    white-space: nowrap;
  }
  .control-panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    padding: 14px;
    min-height: 132px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  }
  .control-panel .title {
    color: var(--ink);
    font-size: 0.94rem;
    font-weight: 760;
    margin-bottom: 7px;
  }
  .control-panel .text {
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.45;
  }
  .workflow-step {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 11px;
    background: #ffffff;
    min-height: 78px;
  }
  .workflow-step strong {
    display: block;
    color: var(--ink);
    margin-bottom: 4px;
  }
  div[data-testid="stMetric"] {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px 12px;
    background: #ffffff;
  }
  div[data-testid="stMetricLabel"] p {
    color: var(--muted);
    font-weight: 650;
  }
  .stTabs [data-baseweb="tab-list"] {
    gap: 18px;
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
  .system-table {
    width: 100%;
    border-collapse: collapse;
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
    font-size: 0.88rem;
  }
  .system-table th {
    text-align: left;
    color: #475467;
    background: #f8fafc;
    border-bottom: 1px solid var(--line);
    padding: 9px 10px;
    font-size: 0.75rem;
    text-transform: uppercase;
  }
  .system-table td {
    color: #344054;
    border-bottom: 1px solid #eef2f6;
    padding: 9px 10px;
    vertical-align: top;
  }
  .system-table tr:last-child td {
    border-bottom: 0;
  }
  .sidebar-title {
    color: #ffffff;
    font-size: 1.05rem;
    font-weight: 750;
    margin-bottom: 4px;
  }
  .sidebar-muted {
    color: #cbd5e1;
    font-size: 0.82rem;
    margin-bottom: 12px;
  }
  @media (max-width: 760px) {
    .topbar {
      display: block;
    }
    .topbar h1 {
      font-size: 1.35rem;
    }
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


def render_topbar(final_metrics: Dict[str, Any], guardrail: Dict[str, Any]) -> None:
    st.markdown(
        f"""
<div class="topbar">
  <div class="topbar-title">
    <div class="brandmark">CR</div>
    <div>
      <div class="product-label">Verified Credit Research Agent</div>
      <h1>Credit Research Workbench</h1>
      <p>SEC filing research, deterministic financial verification, and auditable workpaper controls.</p>
    </div>
  </div>
  <div class="badge-row">
    <span class="badge good">Guardrail: {final_metrics.get("final_answer_numeric_guardrail", "n/a")}</span>
    <span class="badge">ReAct calls: {final_metrics.get("phase4_tool_call_count", "n/a")}</span>
    <span class="badge">Blocked claims: {guardrail.get("blocked_count", "n/a")}</span>
    <span class="badge">SEC companyfacts</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div class="command-strip">
  <div class="left">
    <span class="command-label">Environment</span>
    <span class="control-chip">Demo workspace</span>
    <span class="control-chip">Read-only artifacts</span>
    <span class="control-chip">SEC companyfacts enabled</span>
  </div>
  <div class="right">
    <span class="command-label">Controls</span>
    <span class="control-chip ok">Numeric guardrail {final_metrics.get("final_answer_numeric_guardrail", "n/a")}</span>
    <span class="control-chip ok">Semantic critic {final_metrics.get("phase5_semantic_approved", "n/a")}</span>
    <span class="control-chip">{guardrail.get("blocked_count", "n/a")} blocked claims</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


PAGE_META = {
    "Control Room": {
        "code": "01",
        "nav": "01  Control Room",
        "description": "Operating dashboard, system controls, and current validation status.",
    },
    "Research Console": {
        "code": "02",
        "nav": "02  Research Console",
        "description": "Live SEC companyfacts workflow for ticker-level deterministic analysis.",
    },
    "Workpaper Audit": {
        "code": "03",
        "nav": "03  Workpaper Audit",
        "description": "Frozen M3 final brief, trace metrics, and ReAct tool ledger.",
    },
    "Model Controls": {
        "code": "04",
        "nav": "04  Model Controls",
        "description": "Numeric guardrail and semantic critic review outputs.",
    },
    "System Architecture": {
        "code": "05",
        "nav": "05  System Architecture",
        "description": "End-to-end system flow and LLM/tool responsibility boundary.",
    },
}


def render_sidebar(final_metrics: Dict[str, Any], guardrail: Dict[str, Any]) -> str:
    with st.sidebar:
        st.markdown(
            """
<div class="sidebar-title">Research Operations</div>
<div class="sidebar-muted">Demo environment for analyst review and interview walkthroughs.</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("**Modules**")
        selected_page = st.radio(
            "Primary navigation",
            list(PAGE_META.keys()),
            index=0,
            format_func=lambda page: PAGE_META[page]["nav"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.markdown("**Control Status**")
        st.markdown(f"- Numeric guardrail: `{final_metrics.get('final_answer_numeric_guardrail', 'n/a')}`")
        st.markdown(f"- Blocked claims: `{guardrail.get('blocked_count', 'n/a')}`")
        st.markdown(f"- Semantic critic: `{final_metrics.get('phase5_semantic_approved', 'n/a')}`")
        st.markdown(f"- Tool calls: `{final_metrics.get('phase4_tool_call_count', 'n/a')}`")
        st.markdown("---")
        st.markdown("**Boundary**")
        st.markdown(
            "LLM stages handle planning, query rewrite, synthesis, and semantic review. "
            "Python tools execute retrieval, calculations, verification, guardrails, and trace persistence."
        )
        return selected_page


def render_module_header(page: str) -> None:
    meta = PAGE_META[page]
    st.markdown(
        f"""
<div class="module-header">
  <div>
    <strong>{page}</strong>
    <span>{meta["description"]}</span>
  </div>
  <div class="module-code">MODULE {meta["code"]}</div>
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
    st.dataframe(rows, width="stretch", hide_index=True)


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
    st.markdown('<div class="section-kicker">Research console</div>', unsafe_allow_html=True)
    st.subheader("Live SEC companyfacts analysis")
    st.markdown(
        """
<div class="callout">
  Read-only deterministic workflow. The console retrieves SEC structured facts,
  maps XBRL concepts, calculates verified changes, and writes no local run artifacts.
</div>
""",
            unsafe_allow_html=True,
        )

    form_col, guide_col = st.columns([1.05, 0.95], gap="large")

    with form_col:
        with st.container(border=True):
            st.markdown("**Research request**")
            sample_label = st.selectbox("Load verified demo preset", list(LIVE_SAMPLE_CASES.keys()))
            sample_ticker, sample_theme, sample_years = LIVE_SAMPLE_CASES[sample_label]
            with st.form("live_sec_analysis_form"):
                cols = st.columns([0.8, 1.2, 1])
                company_query = cols[0].text_input(
                    "Company or ticker",
                    value=sample_ticker,
                    help=(
                        "Enter a ticker or company name, such as AAPL, Apple, "
                        "JP Morgan, Google, Microsoft, Ford, or Meta."
                    ),
                ).strip()
                theme_label = cols[1].selectbox(
                    "Risk theme",
                    list(RISK_THEMES.keys()),
                    index=list(RISK_THEMES.keys()).index(sample_theme),
                )
                year_text = cols[2].text_input("Fiscal years", value=sample_years)
                include_llm_workpaper = st.checkbox(
                    "Generate detailed LLM stage workpaper",
                    value=False,
                    help=(
                        "Optional Bedrock mode. The LLM writes stage-level analyst notes "
                        "after deterministic SEC/XBRL facts are extracted; numeric lines are guarded."
                    ),
                )
                submitted = st.form_submit_button("Run Analysis", type="primary", width="stretch")

    with guide_col:
        st.markdown(
            """
<div class="control-panel">
  <div class="title">Execution controls</div>
  <div class="text">
    Enter either a ticker or a company name. The resolver standardizes the input
    to SEC ticker, CIK, and company name before companyfacts retrieval. Presets
    are demo shortcuts, not the full supported universe.
  </div>
  <br>
  <div class="badge-row">
    <span class="badge">name resolver</span>
    <span class="badge">read-only</span>
    <span class="badge">SEC companyfacts</span>
    <span class="badge">verified deltas</span>
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

    if not company_query:
        st.error("Company or ticker is required.")
        return
    if len(years) < 1:
        st.error("At least one fiscal year is required.")
        return

    analyzer = get_universal_analyzer()
    spinner_text = f"Resolving company and fetching SEC companyfacts for {company_query}..."
    if include_llm_workpaper:
        spinner_text = f"Resolving company, fetching SEC facts, and generating guarded LLM workpaper for {company_query}..."
    with st.spinner(spinner_text):
        result = analyzer.analyze(
            company_query,
            RISK_THEMES[theme_label],
            years,
            include_llm_workpaper=include_llm_workpaper,
        )

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
        st.subheader("Verified change register")
        st.dataframe(changes, width="stretch", hide_index=True)

    tabs = ["Brief", "Fact Register"]
    if result.stage_workpaper:
        tabs.append("LLM Stage Workpaper")
    tabs.append("Trace")
    result_tabs = st.tabs(tabs)
    with result_tabs[0]:
        if result.brief:
            st.markdown(result.brief)
        else:
            st.warning("No brief was generated.")
    with result_tabs[1]:
        rows = metric_rows(result)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("No metrics were extracted for the selected years/theme.")
    tab_index = 2
    if result.stage_workpaper:
        with result_tabs[2]:
            render_stage_workpaper(result.stage_workpaper)
        tab_index = 3
    with result_tabs[tab_index]:
        st.json(result.trace)


def render_stage_workpaper(stage_workpaper: List[Dict[str, Any]]) -> None:
    st.subheader("Detailed LLM stage workpaper")
    st.caption(
        "LLM-written analyst notes generated after deterministic SEC/XBRL extraction. "
        "Financial-number lines are checked against the verified fact set."
    )
    summary_rows = [
        {
            "stage": item.get("stage"),
            "status": item.get("status"),
            "numeric_guardrail": item.get("guardrail_status"),
            "blocked_lines": len(item.get("blocked_lines", [])),
        }
        for item in stage_workpaper
    ]
    st.dataframe(summary_rows, width="stretch", hide_index=True)
    for item in stage_workpaper:
        with st.expander(item.get("stage", "Stage workpaper"), expanded=True):
            st.markdown(item.get("analysis", ""))
            blocked = item.get("blocked_lines", [])
            if blocked:
                st.warning(f"{len(blocked)} LLM line(s) removed by numeric guardrail.")
                with st.expander("Removed lines"):
                    for line in blocked:
                        st.write(line)


def render_m5_smoke_summary() -> None:
    st.subheader("Validation monitor")
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
        st.dataframe(rows, width="stretch", hide_index=True)


def render_overview(final_metrics: Dict[str, Any], guardrail: Dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Control room</div>', unsafe_allow_html=True)
    st.subheader("Credit research operating dashboard")

    cols = st.columns(4)
    with cols[0]:
        status_card("Live SEC mode", "Ready", "companyfacts path")
    with cols[1]:
        status_card("M3 ReAct calls", final_metrics.get("phase4_tool_call_count", "n/a"), "audited tool chain")
    with cols[2]:
        status_card("Final guardrail", final_metrics.get("final_answer_numeric_guardrail", "n/a"), "unsupported numbers blocked")
    with cols[3]:
        status_card("Smoke validation", "Pass", "AAPL, TSLA, NVDA")

    panel_cols = st.columns(3, gap="large")
    with panel_cols[0]:
        st.markdown(
            """
<div class="control-panel">
  <div class="title">Research intake</div>
  <div class="text">Analyst submits a ticker, risk theme, and fiscal years. The workbench routes the request to structured SEC facts or the frozen M3 workpaper package.</div>
</div>
""",
            unsafe_allow_html=True,
        )
    with panel_cols[1]:
        st.markdown(
            """
<div class="control-panel">
  <div class="title">Verification layer</div>
  <div class="text">Financial numbers are extracted, mapped, calculated, and checked by deterministic Python paths before they can appear as conclusions.</div>
</div>
""",
            unsafe_allow_html=True,
        )
    with panel_cols[2]:
        st.markdown(
            """
<div class="control-panel">
  <div class="title">Audit package</div>
  <div class="text">The system exposes workpaper artifacts, tool calls, guardrail outputs, semantic critic results, and trace metrics for review.</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### Operating model")
    st.markdown(
        """
<table class="system-table">
  <tr><th>Capability</th><th>Enterprise control</th><th>Current evidence</th></tr>
  <tr>
    <td>Agentic research workflow</td>
    <td>LLM plans, rewrites queries, calls approved tools, and records decision summaries.</td>
    <td>M3 Bedrock ReAct run with 9 deterministic tool calls.</td>
  </tr>
  <tr>
    <td>Financial number discipline</td>
    <td>Numeric claims require deterministic verification or are blocked before final output.</td>
    <td>Phase 2 guardrail blocked an unsupported draft, repair passed final guardrail.</td>
  </tr>
  <tr>
    <td>Live structured data path</td>
    <td>SEC companyfacts are retrieved and mapped through configured XBRL concepts.</td>
    <td>M5 smoke passed for AAPL, TSLA, and NVDA.</td>
  </tr>
  <tr>
    <td>Auditability</td>
    <td>Final answer, tool trace, critic report, and guardrail result are inspectable artifacts.</td>
    <td>Committed M3 workpaper package loaded from examples/m3_full_demo.</td>
  </tr>
</table>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Why this is not a normal RAG bot")
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown(
            """
<div class="panel">
  <h3>Workflow distinction</h3>
  <p class="small-muted">
    Ordinary RAG retrieves text and summarizes it. This system separates LLM
    judgment from financial controls: the LLM plans and synthesizes, while
    deterministic tools execute retrieval, verification, calculations, guardrails,
    and trace persistence.
  </p>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
<div class="panel">
  <h3>Analyst-facing controls</h3>
  <p class="small-muted">
    The workbench exposes the brief, evidence path, tool timeline, blocked claims,
    semantic critic decision, and live SEC fact register so reviewers can inspect
    how the answer was produced.
  </p>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### M3 guardrail snapshot")
    render_metric_row(final_metrics, guardrail)


def render_workpaper(final_answer: str, trace_log: Dict[str, Any], tool_trace: Dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Run audit</div>', unsafe_allow_html=True)
    st.subheader("Frozen M3 workpaper package")
    brief_tab, trace_tab, tools_tab = st.tabs(["Final Brief", "Trace Metrics", "Tool Timeline"])
    with brief_tab:
        st.markdown(final_answer)
    with trace_tab:
        st.subheader("Control metrics")
        final_metrics = trace_log.get("final_metrics", {})
        cols = st.columns(4)
        cols[0].metric("Loop phase", "M3")
        cols[1].metric("Tool calls", str(final_metrics.get("phase4_tool_call_count", "n/a")))
        cols[2].metric("Repair run", str(final_metrics.get("phase2_repaired", "n/a")))
        cols[3].metric("Semantic approved", str(final_metrics.get("phase5_semantic_approved", "n/a")))
        with st.expander("Trace JSON"):
            st.json(trace_log)
    with tools_tab:
        st.subheader("Phase 4 ReAct tool ledger")
        st.caption(f"Tool call count: {tool_trace.get('tool_call_count', 'n/a')}")
        render_tool_timeline(tool_events(tool_trace))
        with st.expander("Raw tool trace JSON"):
            st.json(tool_trace)


def render_guardrails(guardrail: Dict[str, Any], semantic_critic: Dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Model controls</div>', unsafe_allow_html=True)
    st.subheader("Numeric and semantic review")
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
    st.markdown('<div class="section-kicker">System design</div>', unsafe_allow_html=True)
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
        page_title="Credit Research Workbench",
        page_icon=None,
        layout="wide",
    )
    inject_css()

    if not artifact_available():
        st.error(f"Static demo artifacts were not found at {ARTIFACT_DIR}.")
        st.stop()

    final_answer = read_text("final_answer.md")
    trace_log = read_json("trace_log.json")
    tool_trace = read_json("phase4_react_tool_trace.json")
    guardrail = read_json("final_answer_numeric_guardrail.json")
    semantic_critic = read_json("phase5_semantic_critic.json")
    final_metrics = trace_log.get("final_metrics", {})

    selected_page = render_sidebar(final_metrics, guardrail)
    render_topbar(final_metrics, guardrail)
    render_module_header(selected_page)

    if selected_page == "Control Room":
        render_overview(final_metrics, guardrail)
    elif selected_page == "Research Console":
        render_live_sec_analysis()
    elif selected_page == "Workpaper Audit":
        render_workpaper(final_answer, trace_log, tool_trace)
    elif selected_page == "Model Controls":
        render_guardrails(guardrail, semantic_critic)
    elif selected_page == "System Architecture":
        render_architecture()


if __name__ == "__main__":
    main()
