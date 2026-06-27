"""Streamlit demo UI for the Verified Credit Research Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from credit_research_agent.llm_stage_workpaper import generate_consolidated_stage_workpaper
from credit_research_agent.universal_analyzer import AnalysisResult, UniversalCreditAnalyzer


ROOT = Path(__file__).resolve().parent
M5_SMOKE_PATH = ROOT / "examples" / "m5_live_smoke.json"
LIVE_RUN_KEY = "current_live_analysis_run"

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

FISCAL_YEAR_OPTIONS = [2025, 2024, 2023, 2022, 2021, 2020, 2019]

LIVE_SAMPLE_CASES = {
    "Apple leverage: AAPL 2023-2024": ("AAPL", ["Leverage Analysis"], [2024, 2023]),
    "Tesla leverage: TSLA 2023-2024": ("TSLA", ["Leverage Analysis"], [2024, 2023]),
    "NVIDIA leverage: NVDA 2024-2025": ("NVDA", ["Leverage Analysis"], [2025, 2024]),
    "Custom": ("", ["Leverage Analysis"], [2024, 2023]),
}
DEFAULT_LIVE_PRESET = next(iter(LIVE_SAMPLE_CASES))
CUSTOM_LIVE_PRESET = "Custom"
LIVE_PRESET_KEY = "live_demo_preset"
LIVE_APPLIED_PRESET_KEY = "live_applied_demo_preset"
LIVE_PENDING_PRESET_KEY = "live_pending_demo_preset"
LIVE_COMPANY_KEY = "live_company_query"
LIVE_THEMES_KEY = "live_theme_pills"
LIVE_YEARS_KEY = "live_year_pills"


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
  .console-hero {
    border: 1px solid #cfd6e3;
    border-top: 3px solid var(--accent);
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border-radius: 8px;
    padding: 16px 18px;
    margin: 8px 0 14px;
    display: flex;
    justify-content: space-between;
    gap: 20px;
    align-items: flex-start;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
  }
  .console-hero .title {
    color: var(--ink);
    font-size: 1.02rem;
    font-weight: 780;
    margin-bottom: 5px;
  }
  .console-hero .text {
    color: #475467;
    font-size: 0.86rem;
    line-height: 1.5;
    max-width: 840px;
  }
  .console-hero .mode {
    border: 1px solid #b8c2d3;
    background: #111827;
    color: #ffffff;
    border-radius: 7px;
    padding: 7px 10px;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }
  .request-panel {
    border: 1px solid #cfd6e3;
    border-radius: 8px;
    background: #ffffff;
    padding: 0;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
    overflow: hidden;
  }
  .request-panel-header {
    border-bottom: 1px solid var(--line);
    background: #f8fafc;
    padding: 13px 15px;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
  }
  .request-panel-header .title {
    color: var(--ink);
    font-size: 0.96rem;
    font-weight: 800;
    margin-bottom: 3px;
  }
  .request-panel-header .subtitle {
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.4;
  }
  .request-panel-header .stamp {
    border: 1px solid #cfd6e3;
    background: #ffffff;
    color: #344054;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
  }
  .request-panel-body {
    padding: 14px 15px 15px;
  }
  .field-band {
    border-top: 1px solid #e3e8ef;
    padding: 13px 0 0;
    margin: 14px 0 8px;
  }
  .field-band-title {
    color: #344054;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0;
  }
  .execution-rail {
    border: 1px solid #cfd6e3;
    border-radius: 8px;
    background: #ffffff;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
    overflow: hidden;
  }
  .execution-rail-header {
    background: #111827;
    color: #ffffff;
    padding: 14px 15px;
  }
  .execution-rail-header .title {
    color: #ffffff;
    font-size: 0.96rem;
    font-weight: 800;
    margin-bottom: 4px;
  }
  .execution-rail-header .text {
    color: #cbd5e1;
    font-size: 0.78rem;
    line-height: 1.45;
  }
  .execution-rail-body {
    padding: 12px 14px 14px;
  }
  .rail-row {
    border-bottom: 1px solid #eef2f6;
    padding: 9px 0;
    display: grid;
    grid-template-columns: 88px 1fr;
    gap: 10px;
    align-items: start;
  }
  .rail-row:last-child {
    border-bottom: 0;
  }
  .rail-label {
    color: #667085;
    font-size: 0.7rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .rail-value {
    color: #344054;
    font-size: 0.82rem;
    line-height: 1.42;
  }
  .rail-checks {
    display: grid;
    grid-template-columns: 1fr;
    gap: 7px;
    margin-top: 8px;
  }
  .rail-check {
    border: 1px solid #dbe4ee;
    background: #f8fafc;
    color: #344054;
    border-radius: 7px;
    padding: 7px 9px;
    font-size: 0.78rem;
    font-weight: 650;
  }
  .rail-check strong {
    color: var(--good);
    margin-right: 5px;
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
  .selector-title {
    color: var(--ink);
    font-size: 0.85rem;
    font-weight: 760;
    margin-bottom: 2px;
  }
  .selector-help {
    color: var(--muted);
    font-size: 0.76rem;
    margin-bottom: 8px;
  }
  div[data-testid="stPills"] button {
    border-radius: 7px;
    font-weight: 700;
    min-height: 34px;
  }
  div[data-testid="stForm"] {
    border: 0;
    padding: 0;
    background: transparent;
  }
  div[data-testid="stForm"] label p {
    color: #344054;
    font-size: 0.82rem;
    font-weight: 730;
  }
  div[data-testid="stTextInput"] input,
  div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    border-radius: 7px;
  }
  div[data-testid="stFormSubmitButton"] button {
    min-height: 42px;
    border-radius: 7px;
    font-weight: 800;
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
    .console-hero {
      display: block;
    }
    .console-hero .mode {
      display: inline-block;
      margin-top: 10px;
    }
    .rail-row {
      grid-template-columns: 1fr;
      gap: 3px;
    }
  }
</style>
""",
        unsafe_allow_html=True,
    )


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


def empty_run_summary() -> Dict[str, Any]:
    """Return dashboard values before a user runs a case."""
    return {
        "case_label": "No active case",
        "run_status": "empty",
        "guardrail_status": "not run",
        "blocked_claims": "n/a",
        "semantic_status": "not run",
        "tool_calls": "n/a",
        "verified_facts": 0,
        "themes": [],
        "years": [],
    }


def current_run() -> Optional[Dict[str, Any]]:
    """Read the active live analysis from Streamlit session state."""
    run = st.session_state.get(LIVE_RUN_KEY)
    return run if isinstance(run, dict) else None


def summarize_run(run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize the active run for top-level dashboard controls."""
    if not run:
        return empty_run_summary()

    results: List[AnalysisResult] = run.get("results", [])
    theme_labels: List[str] = run.get("theme_labels", [])
    consolidated_workpaper = run.get("consolidated_workpaper") or []
    stage_workpapers = list(consolidated_workpaper)
    for result in results:
        stage_workpapers.extend(result.stage_workpaper or [])

    first_result = results[0] if results else None
    statuses = [result.status for result in results]
    blocked_claims = sum(len(stage.get("blocked_lines", [])) for stage in stage_workpapers)
    guardrail_status = "not run"
    if stage_workpapers:
        guardrail_status = "block" if blocked_claims else "pass"

    return {
        "case_label": run.get("case_label", "Live analysis"),
        "run_status": "success" if statuses and all(status == "success" for status in statuses) else "review",
        "guardrail_status": guardrail_status,
        "blocked_claims": blocked_claims if stage_workpapers else "n/a",
        "semantic_status": "not run",
        "tool_calls": "SEC statements + companyfacts",
        "verified_facts": sum(len(items) for result in results for items in result.metrics.values()),
        "themes": theme_labels,
        "years": first_result.years if first_result else [],
        "company": first_result.company if first_result else "",
        "ticker": first_result.ticker if first_result else "",
    }


def render_topbar(summary: Dict[str, Any]) -> None:
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
    <span class="badge good">Guardrail: {summary.get("guardrail_status", "not run")}</span>
    <span class="badge">Run: {summary.get("run_status", "empty")}</span>
    <span class="badge">Blocked claims: {summary.get("blocked_claims", "n/a")}</span>
    <span class="badge">SEC statements</span>
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
    <span class="control-chip">SEC statement extraction enabled</span>
  </div>
  <div class="right">
    <span class="command-label">Controls</span>
    <span class="control-chip ok">Numeric guardrail {summary.get("guardrail_status", "not run")}</span>
    <span class="control-chip ok">Semantic critic {summary.get("semantic_status", "not run")}</span>
    <span class="control-chip">{summary.get("blocked_claims", "n/a")} blocked claims</span>
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
        "description": "Live SEC statement-first workflow for ticker-level deterministic analysis.",
    },
    "Workpaper Audit": {
        "code": "03",
        "nav": "03  Workpaper Audit",
        "description": "Current case brief, fact register, trace, and guarded workpaper.",
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


def render_sidebar(summary: Dict[str, Any]) -> str:
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
        st.markdown(f"- Active case: `{summary.get('case_label', 'No active case')}`")
        st.markdown(f"- Numeric guardrail: `{summary.get('guardrail_status', 'not run')}`")
        st.markdown(f"- Blocked claims: `{summary.get('blocked_claims', 'n/a')}`")
        st.markdown(f"- Verified facts: `{summary.get('verified_facts', 0)}`")
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


def render_metric_row(summary: Dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Run status", str(summary.get("run_status", "empty")))
    cols[1].metric("Verified facts", str(summary.get("verified_facts", 0)))
    cols[2].metric("Themes", str(len(summary.get("themes", []))))
    cols[3].metric("Years", ", ".join(str(year) for year in summary.get("years", [])) or "n/a")

    cols = st.columns(3)
    cols[0].metric("Numeric guardrail", str(summary.get("guardrail_status", "not run")))
    cols[1].metric("Blocked claims", str(summary.get("blocked_claims", "n/a")))
    cols[2].metric("Semantic review", str(summary.get("semantic_status", "not run")))


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


def pill_selector(
    *,
    title: str,
    help_text: str,
    options: List[Any],
    defaults: List[Any],
    key_prefix: str,
) -> List[Any]:
    """Render a compact multi-select pill selector and return selected values."""
    with st.container(border=True):
        st.markdown(
            f"""
<div class="selector-title">{title}</div>
<div class="selector-help">{help_text}</div>
""",
            unsafe_allow_html=True,
        )
        selected = st.pills(
            title,
            options,
            selection_mode="multi",
            default=None if key_prefix in st.session_state else defaults,
            key=key_prefix,
            label_visibility="collapsed",
        )
    return list(selected or [])


def ensure_live_form_state() -> None:
    """Initialize live analysis controls once without overwriting user input."""
    pending_preset = st.session_state.pop(LIVE_PENDING_PRESET_KEY, None)
    if pending_preset:
        st.session_state[LIVE_PRESET_KEY] = pending_preset
        st.session_state[LIVE_APPLIED_PRESET_KEY] = pending_preset
    if LIVE_PRESET_KEY not in st.session_state:
        st.session_state[LIVE_PRESET_KEY] = DEFAULT_LIVE_PRESET
    if LIVE_COMPANY_KEY not in st.session_state:
        ticker, themes, years = LIVE_SAMPLE_CASES[DEFAULT_LIVE_PRESET]
        st.session_state[LIVE_COMPANY_KEY] = ticker
        st.session_state[LIVE_THEMES_KEY] = themes
        st.session_state[LIVE_YEARS_KEY] = years
        st.session_state[LIVE_APPLIED_PRESET_KEY] = DEFAULT_LIVE_PRESET


def apply_selected_preset_if_changed() -> None:
    """Apply preset values only when the preset selector changes."""
    sample_label = st.session_state.get(LIVE_PRESET_KEY, DEFAULT_LIVE_PRESET)
    if st.session_state.get(LIVE_APPLIED_PRESET_KEY) == sample_label:
        return
    if sample_label == CUSTOM_LIVE_PRESET:
        st.session_state[LIVE_APPLIED_PRESET_KEY] = sample_label
        return
    ticker, themes, years = LIVE_SAMPLE_CASES[sample_label]
    st.session_state[LIVE_COMPANY_KEY] = ticker
    st.session_state[LIVE_THEMES_KEY] = themes
    st.session_state[LIVE_YEARS_KEY] = years
    st.session_state[LIVE_APPLIED_PRESET_KEY] = sample_label


def mark_custom_preset_if_needed(
    company_query: str,
    theme_labels: List[str],
    years: List[int],
) -> None:
    """Show Custom when submitted controls no longer match a preset."""
    normalized_company = company_query.strip().upper()
    normalized_years = sorted(years)
    for preset_name, (ticker, themes, preset_years) in LIVE_SAMPLE_CASES.items():
        if preset_name == CUSTOM_LIVE_PRESET:
            continue
        if (
            normalized_company == ticker.upper()
            and list(theme_labels) == list(themes)
            and normalized_years == sorted(preset_years)
        ):
            st.session_state[LIVE_PENDING_PRESET_KEY] = preset_name
            return
    st.session_state[LIVE_PENDING_PRESET_KEY] = CUSTOM_LIVE_PRESET


def render_live_sec_analysis() -> None:
    st.markdown('<div class="section-kicker">Research console</div>', unsafe_allow_html=True)
    st.subheader("Live SEC statement analysis")
    st.markdown(
        """
<div class="console-hero">
  <div>
    <div class="title">Statement-first credit research workflow</div>
    <div class="text">
      Resolve a public issuer, retrieve SEC 10-K statement tables and companyfacts,
      verify financial metrics deterministically, then generate analyst-ready
      coverage diagnostics and source registers.
    </div>
  </div>
  <div class="mode">Read-only live SEC</div>
</div>
""",
            unsafe_allow_html=True,
        )

    form_col, guide_col = st.columns([1.18, 0.82], gap="large")

    with form_col:
        ensure_live_form_state()
        st.markdown(
            """
<div class="request-panel">
  <div class="request-panel-header">
    <div>
      <div class="title">Research request</div>
      <div class="subtitle">Define the issuer, risk lens, and fiscal period for deterministic SEC analysis.</div>
    </div>
    <div class="stamp">Input deck</div>
  </div>
  <div class="request-panel-body">
""",
            unsafe_allow_html=True,
        )
        with st.container():
            st.selectbox(
                "Load verified demo preset",
                list(LIVE_SAMPLE_CASES.keys()),
                key=LIVE_PRESET_KEY,
            )
            apply_selected_preset_if_changed()
            with st.form("live_sec_analysis_form"):
                st.markdown(
                    """
<div class="field-band">
  <div class="field-band-title">Issuer resolution</div>
</div>
""",
                    unsafe_allow_html=True,
                )
                company_query = st.text_input(
                    "Company or ticker",
                    key=LIVE_COMPANY_KEY,
                    help=(
                        "Enter a ticker or company name, such as AAPL, Apple, "
                        "JP Morgan, Google, Microsoft, Ford, or Meta."
                    ),
                ).strip()
                st.markdown(
                    """
<div class="field-band">
  <div class="field-band-title">Analysis scope</div>
</div>
""",
                    unsafe_allow_html=True,
                )
                selector_cols = st.columns([1.15, 0.85], gap="medium")
                with selector_cols[0]:
                    theme_labels = pill_selector(
                        title="Risk themes",
                        help_text="Select one or more credit risk lenses.",
                        options=list(RISK_THEMES.keys()),
                        defaults=st.session_state.get(LIVE_THEMES_KEY, ["Leverage Analysis"]),
                        key_prefix=LIVE_THEMES_KEY,
                    )
                with selector_cols[1]:
                    years = pill_selector(
                        title="Fiscal years",
                        help_text="Two or more years enable trend analysis.",
                        options=FISCAL_YEAR_OPTIONS,
                        defaults=st.session_state.get(LIVE_YEARS_KEY, [2024, 2023]),
                        key_prefix=LIVE_YEARS_KEY,
                    )
                st.markdown(
                    """
<div class="field-band">
  <div class="field-band-title">Optional analyst workpaper</div>
</div>
""",
                    unsafe_allow_html=True,
                )
                include_llm_workpaper = st.checkbox(
                    "Generate detailed LLM stage workpaper",
                    value=False,
                    help=(
                        "Optional Bedrock mode. The LLM writes stage-level analyst notes "
                        "after deterministic SEC/XBRL facts are extracted; numeric lines are guarded. "
                        "Multi-theme runs use one consolidated LLM synthesis."
                    ),
                )
                submitted = st.form_submit_button("Run Analysis", type="primary", width="stretch")
        st.markdown("</div></div>", unsafe_allow_html=True)

    with guide_col:
        st.markdown(
            """
<div class="execution-rail">
  <div class="execution-rail-header">
    <div class="title">Execution controls</div>
    <div class="text">The run is deterministic by default. LLM workpapers are optional and remain downstream of verified SEC facts.</div>
  </div>
  <div class="execution-rail-body">
    <div class="rail-row">
      <div class="rail-label">Resolver</div>
      <div class="rail-value">Ticker or company name is standardized to SEC ticker, CIK, and registrant name before analysis.</div>
    </div>
    <div class="rail-row">
      <div class="rail-label">Sources</div>
      <div class="rail-value">10-K statement tables first; companyfacts is used for cross-checking and fallback.</div>
    </div>
    <div class="rail-row">
      <div class="rail-label">Controls</div>
      <div class="rail-value">Risk themes and fiscal years are controlled selections. Multiple themes run as one analysis set.</div>
    </div>
    <div class="rail-checks">
      <div class="rail-check"><strong>OK</strong> read-only SEC workflow</div>
      <div class="rail-check"><strong>OK</strong> deterministic calculations</div>
      <div class="rail-check"><strong>OK</strong> statement source register</div>
      <div class="rail-check"><strong>OK</strong> coverage diagnostics</div>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    if not submitted:
        run = current_run()
        if run:
            st.divider()
            st.subheader("Current analysis result")
            render_live_results(
                run.get("results", []),
                run.get("theme_labels", []),
                run.get("consolidated_workpaper") or [],
            )
        else:
            render_m5_smoke_summary()
        return

    if not company_query:
        st.error("Company or ticker is required.")
        return
    if not theme_labels:
        st.error("Select at least one risk theme.")
        return
    if len(years) < 1:
        st.error("At least one fiscal year is required.")
        return
    years = sorted(years)
    use_consolidated_workpaper = include_llm_workpaper and len(theme_labels) > 1
    per_theme_llm_workpaper = include_llm_workpaper and len(theme_labels) == 1

    analyzer = get_universal_analyzer()
    spinner_text = f"Resolving company and fetching SEC companyfacts for {company_query}..."
    if per_theme_llm_workpaper:
        spinner_text = f"Resolving company, fetching SEC facts, and generating guarded LLM workpaper for {company_query}..."
    if use_consolidated_workpaper:
        spinner_text = f"Running deterministic themes and one consolidated guarded LLM workpaper for {company_query}..."
    with st.spinner(spinner_text):
        results = [
            analyzer.analyze(
                company_query,
                RISK_THEMES[theme_label],
                years,
                include_llm_workpaper=per_theme_llm_workpaper,
            )
            for theme_label in theme_labels
        ]
        consolidated_workpaper = (
            generate_consolidated_workpaper(results, theme_labels)
            if use_consolidated_workpaper
            else []
        )

    st.session_state[LIVE_RUN_KEY] = {
        "case_label": f"{company_query} | {', '.join(theme_labels)} | {', '.join(str(year) for year in years)}",
        "company_query": company_query,
        "theme_labels": theme_labels,
        "years": years,
        "include_llm_workpaper": include_llm_workpaper,
        "results": results,
        "consolidated_workpaper": consolidated_workpaper,
    }
    mark_custom_preset_if_needed(company_query, theme_labels, years)
    st.rerun()


def generate_consolidated_workpaper(
    results: List[AnalysisResult],
    theme_labels: List[str],
) -> List[Dict[str, Any]]:
    """Create one guarded LLM workpaper across successful theme results."""
    successful = [
        (result, theme_label)
        for result, theme_label in zip(results, theme_labels)
        if result.status == "success"
    ]
    if not successful:
        return []

    first_result = successful[0][0]
    stage_workpaper = generate_consolidated_stage_workpaper(
        company=first_result.company,
        ticker=first_result.ticker,
        risk_themes=[RISK_THEMES[theme_label] for _, theme_label in successful],
        years=first_result.years,
        analyses=[
            {
                "risk_theme": RISK_THEMES[theme_label],
                "metrics_by_year": result.metrics,
                "deterministic_brief": result.brief,
            }
            for result, theme_label in successful
        ],
    )
    return [stage.to_dict() for stage in stage_workpaper]


def render_live_results(
    results: List[AnalysisResult],
    theme_labels: List[str],
    consolidated_workpaper: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Render one or more live SEC analysis results."""
    if len(results) == 1:
        render_live_result(results[0], theme_labels[0])
        return

    st.divider()
    st.subheader("Analysis run set")
    summary_rows = []
    for result, theme_label in zip(results, theme_labels):
        summary_rows.append(
            {
                "theme": theme_label,
                "company": result.company or "n/a",
                "ticker": result.ticker,
                "status": result.status,
                "verified_facts": sum(len(items) for items in result.metrics.values()),
                "years": ", ".join(str(year) for year in result.years),
                "error": result.error or "",
            }
        )
    st.dataframe(summary_rows, width="stretch", hide_index=True)

    if consolidated_workpaper:
        st.subheader("Consolidated LLM workpaper")
        render_stage_workpaper(consolidated_workpaper)

    theme_tabs = st.tabs(theme_labels)
    for tab, result, theme_label in zip(theme_tabs, results, theme_labels):
        with tab:
            render_live_result(result, theme_label, include_divider=False)


def render_live_result(
    result: AnalysisResult,
    theme_label: str,
    include_divider: bool = True,
) -> None:
    total_metrics = sum(len(items) for items in result.metrics.values())
    status_note = "Ready for analyst review" if result.status == "success" else result.error or "Review trace"

    if include_divider:
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
        if result.brief:
            st.info("A resolution notice was generated in the Brief tab. No financial analysis was run.")

    coverage = metric_coverage(result)
    unavailable_metrics = coverage.get("unavailable_metrics", [])
    if unavailable_metrics:
        st.warning(
            "Coverage limitation: the selected theme requested metric(s) with no "
            f"verified statement/companyfacts source in the selected years: "
            f"{', '.join(unavailable_metrics)}."
        )
    partial_metrics = coverage.get("partial_metrics", [])
    if partial_metrics:
        st.info(
            "Comparability note: some requested metric(s) are available for only "
            f"part of the selected period: {', '.join(partial_metrics)}."
        )
    missing_by_year = coverage.get("missing_metrics_by_year", {})
    if missing_by_year:
        missing_rows = [
            {
                "fiscal_year": year,
                "missing_metrics": ", ".join(metrics),
            }
            for year, metrics in sorted(missing_by_year.items())
        ]
        with st.expander("Metric coverage by fiscal year"):
            st.dataframe(missing_rows, width="stretch", hide_index=True)
            diagnostics = coverage.get("diagnostics", [])
            if diagnostics:
                st.markdown("**Coverage diagnosis**")
                st.dataframe(
                    coverage_diagnostic_rows(diagnostics),
                    width="stretch",
                    hide_index=True,
                )

    resolution_rows = metric_resolution_rows(coverage)
    if resolution_rows:
        with st.expander("Metric source register"):
            st.dataframe(resolution_rows, width="stretch", hide_index=True)

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


def metric_coverage(result: AnalysisResult) -> Dict[str, Any]:
    """Return structured metric coverage details from the analysis trace."""
    for item in result.trace:
        coverage = item.get("metric_coverage")
        if item.get("step") == "extract_companyfacts" and isinstance(coverage, dict):
            return coverage
    return {}


def metric_resolution_rows(coverage: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten statement/companyfacts resolver decisions for analyst review."""
    rows = []
    by_year = coverage.get("metric_resolutions_by_year", {})
    for fiscal_year, resolutions in sorted(by_year.items()):
        for resolution in resolutions:
            selected_fact = resolution.get("selected_fact") or {}
            status = resolution.get("status")
            cross_check = resolution.get("companyfacts_cross_check") or {}
            is_statement = status in {
                "verified_statement",
                "verified_cross_checked",
                "cross_check_mismatch",
            }
            is_calculated = status == "calculated_from_verified_inputs"
            rows.append(
                {
                    "fiscal_year": fiscal_year,
                    "metric": resolution.get("metric_name"),
                    "status": status,
                    "source_type": (
                        "statement"
                        if is_statement
                        else "calculated"
                        if is_calculated
                        else "companyfacts"
                    ),
                    "statement_type": selected_fact.get("statement_type", ""),
                    "row_label": selected_fact.get("row_label", ""),
                    "accepted_concept": resolution.get("accepted_concept") or "",
                    "value": selected_fact.get("value"),
                    "unit": selected_fact.get("unit", ""),
                    "companyfacts_cross_check": cross_check.get("status", ""),
                    "cross_check_difference": cross_check.get("difference"),
                    "basis": resolution.get("decision_basis", ""),
                    "requires_review": resolution.get("requires_review", False),
                }
            )
    return rows


def coverage_diagnostic_rows(diagnostics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten metric coverage diagnostics for analyst review."""
    rows = []
    for item in diagnostics:
        related = item.get("related_companyfact_candidates", [])
        zero_candidates = item.get("zero_value_candidates", [])
        rows.append(
            {
                "metric": item.get("metric_name"),
                "status": item.get("status"),
                "covered_years": ", ".join(str(year) for year in item.get("covered_years", [])),
                "missing_years": ", ".join(str(year) for year in item.get("missing_years", [])),
                "configured_concepts": ", ".join(item.get("configured_concepts", [])),
                "related_concepts": ", ".join(
                    candidate.get("concept", "") for candidate in related[:4]
                ),
                "zero_value_candidates": ", ".join(
                    candidate.get("concept", "") for candidate in zero_candidates[:4]
                ),
                "diagnosis": item.get("diagnosis", ""),
            }
        )
    return rows


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


def render_overview(summary: Dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Control room</div>', unsafe_allow_html=True)
    st.subheader("Credit research operating dashboard")

    cols = st.columns(4)
    with cols[0]:
        status_card("Active case", summary.get("case_label", "No active case"), "current session")
    with cols[1]:
        status_card("Verified facts", summary.get("verified_facts", 0), "SEC companyfacts metrics")
    with cols[2]:
        status_card("Guardrail", summary.get("guardrail_status", "not run"), "LLM numeric controls")
    with cols[3]:
        status_card("Run status", summary.get("run_status", "empty"), summary.get("ticker", "Run a case to populate"))

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
    <td>Populated after a Research Console run; frozen M3 artifacts remain in examples for package review.</td>
  </tr>
  <tr>
    <td>Financial number discipline</td>
    <td>Numeric claims require deterministic verification or are blocked before final output.</td>
    <td>Current live run shows verified facts, calculated metrics, and unavailable metric coverage.</td>
  </tr>
  <tr>
    <td>Live structured data path</td>
    <td>SEC companyfacts are retrieved and mapped through configured XBRL concepts.</td>
    <td>M5 smoke passed for AAPL, TSLA, and NVDA.</td>
  </tr>
  <tr>
    <td>Auditability</td>
    <td>Final answer, tool trace, critic report, and guardrail result are inspectable artifacts.</td>
    <td>Workpaper Audit updates from the current Streamlit session run.</td>
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

    st.markdown("### Current run controls")
    render_metric_row(summary)


def render_empty_current_run(message: str = "Run an analysis from Research Console to populate this page.") -> None:
    """Render an empty state for pages that depend on a live case."""
    st.info(message)
    st.markdown(
        """
<div class="panel">
  <h3>No active workpaper</h3>
  <p class="small-muted">
    The workbench starts empty by design. Select a company, risk theme, and fiscal
    years in Research Console, then run analysis. This page will update to that
    case's brief, fact register, trace, and guarded LLM notes.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_workpaper(run: Optional[Dict[str, Any]]) -> None:
    st.markdown('<div class="section-kicker">Run audit</div>', unsafe_allow_html=True)
    st.subheader("Current case workpaper")
    if not run:
        render_empty_current_run()
        return

    results: List[AnalysisResult] = run.get("results", [])
    theme_labels: List[str] = run.get("theme_labels", [])
    consolidated_workpaper = run.get("consolidated_workpaper") or []
    summary = summarize_run(run)

    cols = st.columns(4)
    cols[0].metric("Company", f"{summary.get('company', '')} ({summary.get('ticker', '')})")
    cols[1].metric("Themes", str(len(theme_labels)))
    cols[2].metric("Verified facts", str(summary.get("verified_facts", 0)))
    cols[3].metric("Guardrail", str(summary.get("guardrail_status", "not run")))

    if consolidated_workpaper:
        st.subheader("Consolidated LLM workpaper")
        render_stage_workpaper(consolidated_workpaper)

    if not results:
        st.warning("No result objects are available for the current run.")
        return

    tabs = st.tabs(theme_labels)
    for tab, result, theme_label in zip(tabs, results, theme_labels):
        with tab:
            render_live_result(result, theme_label, include_divider=False)


def render_guardrails(run: Optional[Dict[str, Any]]) -> None:
    st.markdown('<div class="section-kicker">Model controls</div>', unsafe_allow_html=True)
    st.subheader("Current case numeric and semantic review")
    if not run:
        render_empty_current_run("Run a case to inspect numeric guardrail and LLM-stage controls.")
        return

    results: List[AnalysisResult] = run.get("results", [])
    consolidated_workpaper = run.get("consolidated_workpaper") or []
    stage_workpapers = list(consolidated_workpaper)
    for result in results:
        stage_workpapers.extend(result.stage_workpaper or [])

    if not stage_workpapers:
        st.info(
            "No LLM stage workpaper was requested for the current run. "
            "Deterministic numeric verification still ran through SEC companyfacts extraction."
        )
        coverage_rows = []
        for result in results:
            coverage = metric_coverage(result)
            coverage_rows.append(
                {
                    "theme": result.theme,
                    "requested_metrics": ", ".join(coverage.get("requested_metrics", [])),
                    "direct_xbrl_metrics": ", ".join(coverage.get("direct_xbrl_metrics", [])),
                    "calculated_metrics": ", ".join(coverage.get("calculated_metrics", [])),
                    "unavailable_metrics": ", ".join(coverage.get("unavailable_metrics", [])),
                }
            )
        if coverage_rows:
            st.subheader("Metric coverage controls")
            st.dataframe(coverage_rows, width="stretch", hide_index=True)
        return

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Numeric guardrail")
        summary_rows = [
            {
                "stage": stage.get("stage"),
                "status": stage.get("status"),
                "guardrail_status": stage.get("guardrail_status"),
                "blocked_lines": len(stage.get("blocked_lines", [])),
            }
            for stage in stage_workpapers
        ]
        st.dataframe(summary_rows, width="stretch", hide_index=True)
    with right:
        st.subheader("Semantic critic")
        st.info(
            "Live companyfacts mode uses deterministic numeric controls and optional "
            "LLM-stage numeric guardrails. The M3 semantic critic applies to the frozen "
            "ReAct package, not to this live lightweight run."
        )
        with st.expander("Stage workpaper JSON"):
            st.json(stage_workpapers)


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

    run = current_run()
    summary = summarize_run(run)

    selected_page = render_sidebar(summary)
    render_topbar(summary)
    render_module_header(selected_page)

    if selected_page == "Control Room":
        render_overview(summary)
    elif selected_page == "Research Console":
        render_live_sec_analysis()
    elif selected_page == "Workpaper Audit":
        render_workpaper(current_run())
    elif selected_page == "Model Controls":
        render_guardrails(current_run())
    elif selected_page == "System Architecture":
        render_architecture()


if __name__ == "__main__":
    main()
