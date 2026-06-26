"""Schemas for the M4 MCP integration layer."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    ticker: str = "F"
    years: Optional[List[int]] = None
    sections: Optional[List[str]] = None


class HybridRetrieveRequest(BaseModel):
    query: str
    top_n: int = Field(default=10, ge=1, le=25)
    filters: Optional[RetrievalFilters] = None


class HybridRetrieveResult(BaseModel):
    chunk_id: str
    fiscal_year: int
    section_name: str
    text: str
    citation: str
    score: float


class HybridRetrieveResponse(BaseModel):
    results: List[HybridRetrieveResult]
    supported_ticker: str = "F"
    note: str = "M4.3 MCP retrieval is read-only and currently supports Ford ticker F."


class VerifyNumericClaimRequest(BaseModel):
    ticker: str = "F"
    metric_name: str
    old_year: int
    new_year: int


class VerifyNumericClaimResponse(BaseModel):
    status: str
    old_value: float | None = None
    new_value: float | None = None
    absolute_change: float | None = None
    percentage_change: float | None = None
    source_fact_ids: List[str] = Field(default_factory=list)
    supported_ticker: str = "F"
    note: str = "M4.3 MCP verification is read-only and currently supports Ford ticker F."

