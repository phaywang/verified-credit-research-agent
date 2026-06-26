"""M1/M2 deterministic functions exposed as M3 tools."""

from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
from functools import lru_cache
from typing import Any, Dict, List, Optional

from credit_research_agent.config import DATA_DIR, RUNS_DIR
from credit_research_agent.memory.research_memory import ResearchMemory
from credit_research_agent.retrieval.chunk_store import load_chunks_jsonl
from credit_research_agent.retrieval.hybrid_retriever import HybridRetriever
from credit_research_agent.schemas import TaskSpec, write_json
from credit_research_agent.verification.calculations import (
    calculate_change as deterministic_change,
    calculate_percentage_change,
    direction,
)
from credit_research_agent.verification.fact_extractor import extract_numeric_facts
from credit_research_agent.verification.fact_store import FactStore
from credit_research_agent.verification.numeric_claim_extractor import propose_numeric_claims
from credit_research_agent.verification.numeric_verifier import verify_numeric_claims
from credit_research_agent.m3.guardrails import numeric_guardrail_check as _numeric_guardrail_check


DEFAULT_CHUNK_PATH = DATA_DIR / "processed" / "ford_2023_2025_chunks.jsonl"
DEFAULT_RAW_ROOT = DATA_DIR / "raw" / "sec" / "ford"


@lru_cache(maxsize=4)
def _chunks() -> tuple[Any, ...]:
    chunks = load_chunks_jsonl(DEFAULT_CHUNK_PATH)
    return tuple(chunks)


@lru_cache(maxsize=2)
def _retriever() -> HybridRetriever:
    return HybridRetriever(list(_chunks()))


def hybrid_retrieve(query: str, top_n: int = 10) -> Dict[str, Any]:
    retriever = _retriever()
    results = retriever.retrieve(query, top_n=top_n)
    return {
        "query": query,
        "results": [
            {
                "chunk_id": result.chunk_id,
                "fiscal_year": result.fiscal_year,
                "section_name": result.section_name,
                "rrf_score": result.rrf_score,
                "text_preview": result.text[:500],
                "source_url": result.source_url,
            }
            for result in results
        ],
    }


@lru_cache(maxsize=1)
def _fact_store() -> FactStore:
    chunks = list(_chunks())
    facts = extract_numeric_facts(chunks, DEFAULT_RAW_ROOT, years=(2023, 2025))
    store = FactStore()
    store.add_facts(facts)
    return store


@lru_cache(maxsize=1)
def _all_facts() -> List[Any]:
    chunks = list(_chunks())
    return extract_numeric_facts(chunks, DEFAULT_RAW_ROOT, years=(2023, 2025))


def xbrl_fact_lookup(metric_name: str, fiscal_year: int) -> Optional[Dict[str, Any]]:
    facts = [
        fact
        for fact in _all_facts()
        if fact.metric_name == metric_name
        and fact.fiscal_year == fiscal_year
        and fact.fact_source == "xbrl"
    ]
    if not facts:
        return None
    return facts[0].model_dump(mode="json")


def verify_numeric_claim(metric_name: str, old_year: int, new_year: int) -> Dict[str, Any]:
    store = _fact_store()
    task = TaskSpec(
        company="Ford Motor Company",
        ticker="F",
        cik="0000037996",
        years=[old_year, new_year],
        filing_types=["10-K"],
        risk_theme="debt_liquidity",
        question="How did Ford's debt and liquidity risk change?",
        required_evidence=[],
    )
    claims = [
        claim
        for claim in propose_numeric_claims(task, store)
        if claim.metric_name == metric_name
    ]
    if not claims:
        return {
            "metric_name": metric_name,
            "old_year": old_year,
            "new_year": new_year,
            "status": "not_enough_data",
            "notes": ["No comparable fact pair found."],
        }
    return verify_numeric_claims([claims[0]], store)[0].model_dump(mode="json")


def calculate_change(old_value: float, new_value: float) -> Dict[str, Any]:
    delta = round(deterministic_change(old_value, new_value), 6)
    return {
        "old_value": old_value,
        "new_value": new_value,
        "absolute_change": delta,
        "percentage_change": calculate_percentage_change(old_value, new_value),
        "direction": direction(old_value, new_value),
    }


def query_memory(topic: str = "debt_liquidity") -> Dict[str, Any]:
    memory = ResearchMemory(Path("memory") / "research_memory.json")
    memory.load()
    topic_memory = memory.get_topic_memory("Ford Motor Company", topic)
    if topic_memory is None:
        return {
            "topic": topic,
            "useful_sections": [],
            "successful_queries": [],
            "verified_metrics": [],
        }
    return asdict(topic_memory)


def query_rewrite_helper(
    coverage_gaps: List[str],
    company: str = "Ford",
    years: Optional[List[int]] = None,
) -> Dict[str, Any]:
    years = years or [2023, 2025]
    target_sections = []
    if any("debt" in gap.lower() for gap in coverage_gaps):
        target_sections.extend(["Debt and Commitments", "Total Debt Maturities"])
    if any("liquidity" in gap.lower() for gap in coverage_gaps):
        target_sections.append("Liquidity and Capital Resources")
    if any("management" in gap.lower() for gap in coverage_gaps):
        target_sections.append("Management Discussion and Analysis")
    if not target_sections:
        target_sections = [
            "Liquidity and Capital Resources",
            "Debt and Commitments",
            "Management Discussion and Analysis",
        ]
    query = (
        f"{company} {' '.join(str(year) for year in years)} 10-K "
        + " ".join(target_sections)
        + " debt liquidity capital resources credit facilities"
    )
    return {
        "rewritten_query": query,
        "reasoning_summary": "Fallback rewrite targeted the missing evidence categories.",
        "target_years": years,
        "target_sections": sorted(set(target_sections)),
        "fallback_used": True,
    }


def numeric_guardrail_check(
    brief_text: str,
    verified_facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Check LLM prose for unverified financial numbers."""

    verified_facts = verified_facts or {}
    if isinstance(verified_facts, dict) and "verification_results" in verified_facts:
        verified_results = verified_facts["verification_results"]
    elif isinstance(verified_facts, list):
        verified_results = verified_facts
    elif isinstance(verified_facts, dict):
        verified_results = verified_facts
    else:
        verified_results = []
    return _numeric_guardrail_check(brief_text, verified_results)


def write_workpaper(artifact_name: str, content: Any = None) -> Dict[str, str]:
    path = RUNS_DIR / "m3_phase1_tool_gate" / artifact_name
    write_json(path, content if content is not None else {"note": "No content provided."})
    return {"path": str(path)}
