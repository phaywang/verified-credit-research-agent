"""Helpers for loading and writing M3 workpaper artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from credit_research_agent.config import RUNS_DIR
from credit_research_agent.schemas import write_json


BASE_RUN_ID = "ford_debt_liquidity_2023_2025"
BASE_RUN_DIR = RUNS_DIR / BASE_RUN_ID


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_base_workpapers() -> Dict[str, Any]:
    """Load M2 workpapers used as verified inputs for M3 roles."""

    return {
        "final_answer": (BASE_RUN_DIR / "final_answer.md").read_text(encoding="utf-8"),
        "numeric_verification": read_json(BASE_RUN_DIR / "numeric_verification.json"),
        "evidence_table": read_json(BASE_RUN_DIR / "evidence_table.json"),
        "evaluation_summary": read_json(BASE_RUN_DIR / "evaluation_summary.json"),
        "trace_log": read_json(BASE_RUN_DIR / "trace_log.json"),
    }


def compact_verified_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compact: List[Dict[str, Any]] = []
    for item in results:
        compact.append(
            {
                "claim_id": item.get("claim_id"),
                "metric_name": item.get("metric_name"),
                "status": item.get("status"),
                "old_year": item.get("old_year"),
                "new_year": item.get("new_year"),
                "old_value": item.get("old_value"),
                "new_value": item.get("new_value"),
                "absolute_change": item.get("absolute_change"),
                "percentage_change": item.get("percentage_change"),
                "direction": item.get("direction"),
                "unit": item.get("unit"),
                "evidence": item.get("evidence", []),
            }
        )
    return compact


def compact_evidence(evidence_table: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": item.get("chunk_id"),
            "fiscal_year": item.get("fiscal_year"),
            "section_name": item.get("section_name"),
            "section_type": item.get("section_type"),
            "text_preview": " ".join(str(item.get("text", "")).split())[:700],
            "source_url": item.get("citation", {}).get("source_url"),
        }
        for item in evidence_table[:limit]
    ]


def write_m3_artifact(run_id: str, name: str, content: Any) -> Path:
    path = RUNS_DIR / run_id / name
    if isinstance(content, str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    else:
        write_json(path, content)
    return path
