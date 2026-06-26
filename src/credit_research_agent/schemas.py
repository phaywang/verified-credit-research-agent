"""Shared data schemas for the Milestone 1 agent harness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


CoverageDecision = Literal["sufficient", "rewrite_query", "proceed_with_limitations"]
SupportStatus = Literal["supported", "unsupported", "needs_review"]
TraceStatus = Literal["running", "completed", "failed"]


class JsonModel(BaseModel):
    """Base model with consistent JSON serialization helpers."""

    model_config = ConfigDict(extra="forbid")

    def to_jsonable(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class TaskSpec(JsonModel):
    company: str
    ticker: str
    cik: str
    years: List[int]
    filing_types: List[str]
    risk_theme: str
    question: str
    required_evidence: List[str]


class Plan(JsonModel):
    objective: str
    research_steps: List[str]
    initial_query: str
    max_retrieval_iterations: int = 3


class FilingDocument(JsonModel):
    company: str
    ticker: str
    cik: str
    fiscal_year: int
    filing_type: str
    filing_date: str
    accession_number: str
    source_url: str
    local_path: str
    is_substitution: bool = False
    requested_fiscal_year: int
    requested_filing_type: str
    substitution_note: Optional[str] = None


class FilingSection(JsonModel):
    document: FilingDocument
    section_name: str
    section_type: str
    text: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class FilingChunk(JsonModel):
    company: str
    ticker: str
    cik: str
    fiscal_year: int
    filing_type: str
    section_name: str
    section_type: str
    chunk_id: str
    text: str
    source_url: str
    filing_date: str
    accession_number: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class RetrievalResult(JsonModel):
    chunk_id: str
    query: str
    section_name: str
    fiscal_year: int
    bm25_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    vector_rank: Optional[int] = None
    vector_score: Optional[float] = None
    rrf_score: float = 0.0
    fused_rank: Optional[int] = None
    text: str
    source_url: str
    chunk: Optional[FilingChunk] = None


class Citation(JsonModel):
    source_url: str
    filing_date: str
    accession_number: str
    chunk_id: str


class EvidenceChunk(JsonModel):
    chunk_id: str
    fiscal_year: int
    filing_type: str
    section_name: str
    section_type: str
    reranker_score: float
    rrf_score: float
    evidence_category: List[str]
    text: str
    citation: Citation


class EvidenceCoverage(JsonModel):
    has_2023_evidence: bool = False
    has_2025_evidence: bool = False
    has_debt_evidence: bool = False
    has_liquidity_evidence: bool = False
    has_management_explanation: bool = False
    has_numeric_facts: bool = False
    missing: List[str] = Field(default_factory=list)
    decision: CoverageDecision = "rewrite_query"
    supporting_chunk_ids: Dict[str, List[str]] = Field(default_factory=dict)


class AnswerClaim(JsonModel):
    claim: str
    citation_chunk_ids: List[str]
    support_status: SupportStatus


class FinalAnswer(JsonModel):
    markdown: str
    claims: List[AnswerClaim]
    trace_log_path: str


class CriticReport(JsonModel):
    unsupported_claims: List[AnswerClaim] = Field(default_factory=list)
    needs_repair: bool = False
    notes: List[str] = Field(default_factory=list)


class FinalMetrics(JsonModel):
    citation_coverage: float = 0.0
    evidence_coverage_passed: bool = False
    unsupported_claim_count: int = 0
    retrieval_iterations: int = 0
    rewrite_count: int = 0
    substitution_used: bool = False


class TraceStep(JsonModel):
    state: str
    timestamp: datetime = Field(default_factory=datetime.now)
    summary: Optional[str] = None
    iteration: Optional[int] = None
    query: Optional[str] = None
    tools_called: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    coverage: Optional[Dict[str, Any]] = None
    missing: List[str] = Field(default_factory=list)
    decision: Optional[str] = None
    top_chunks: List[str] = Field(default_factory=list)
    old_query: Optional[str] = None
    new_query: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


class TraceLog(JsonModel):
    run_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    task: str
    task_spec_path: str
    loop_iterations: int = 0
    status: TraceStatus = "running"
    steps: List[TraceStep] = Field(default_factory=list)
    final_metrics: FinalMetrics = Field(default_factory=FinalMetrics)
    artifacts: Dict[str, str] = Field(default_factory=dict)


def write_json(
    path: Path,
    model_or_data: Union[BaseModel, Dict[str, Any], List[Any]],
) -> None:
    """Write a Pydantic model or JSON-compatible object with stable formatting."""

    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(model_or_data, BaseModel):
        data = model_or_data.model_dump(mode="json")
    else:
        data = model_or_data
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
