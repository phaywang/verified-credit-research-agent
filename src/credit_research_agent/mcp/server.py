"""Minimal real MCP server exposing selected M3 deterministic tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from credit_research_agent.m3 import deterministic_tools
from credit_research_agent.mcp.schemas import (
    HybridRetrieveRequest,
    HybridRetrieveResponse,
    HybridRetrieveResult,
    RetrievalFilters,
    VerifyNumericClaimRequest,
    VerifyNumericClaimResponse,
)


TEXT_PREVIEW_CHARS = 700
SUPPORTED_TICKER = "F"


def _validate_ticker(ticker: str) -> None:
    if ticker.upper() != SUPPORTED_TICKER:
        raise ValueError("M4.3 MCP server currently supports only ticker='F'.")


def _matches_filters(result: Dict[str, Any], filters: Optional[RetrievalFilters]) -> bool:
    if filters is None:
        return True
    _validate_ticker(filters.ticker)
    if filters.years and result.get("fiscal_year") not in filters.years:
        return False
    if filters.sections:
        section_name = str(result.get("section_name", "")).lower()
        if not any(section.lower() in section_name for section in filters.sections):
            return False
    return True


def hybrid_retrieve_tool(
    query: str,
    top_n: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read-only MCP wrapper around the M3 hybrid retrieval code path."""

    request = HybridRetrieveRequest(
        query=query,
        top_n=top_n,
        filters=RetrievalFilters(**filters) if filters else None,
    )
    if request.filters:
        _validate_ticker(request.filters.ticker)
    retrieve_top_n = request.top_n
    if request.filters and (request.filters.years or request.filters.sections):
        retrieve_top_n = min(max(request.top_n * 3, request.top_n), 25)
    raw = deterministic_tools.hybrid_retrieve(request.query, top_n=retrieve_top_n)
    compact: List[HybridRetrieveResult] = []
    for item in raw.get("results", []):
        if not _matches_filters(item, request.filters):
            continue
        compact.append(
            HybridRetrieveResult(
                chunk_id=str(item.get("chunk_id", "")),
                fiscal_year=int(item.get("fiscal_year", 0)),
                section_name=str(item.get("section_name", "")),
                text=str(item.get("text_preview", ""))[:TEXT_PREVIEW_CHARS],
                citation=str(item.get("source_url", "")),
                score=float(item.get("rrf_score") or 0.0),
            )
        )
        if len(compact) >= request.top_n:
            break
    return HybridRetrieveResponse(results=compact).model_dump(mode="json")


def verify_numeric_claim_tool(
    ticker: str,
    metric_name: str,
    old_year: int,
    new_year: int,
) -> Dict[str, Any]:
    """Read-only MCP wrapper around the M3 deterministic verifier."""

    request = VerifyNumericClaimRequest(
        ticker=ticker,
        metric_name=metric_name,
        old_year=old_year,
        new_year=new_year,
    )
    _validate_ticker(request.ticker)
    result = deterministic_tools.verify_numeric_claim(
        request.metric_name,
        request.old_year,
        request.new_year,
    )
    source_fact_ids = [
        str(item["fact_id"])
        for item in result.get("evidence", [])
        if item.get("fact_id")
    ]
    return VerifyNumericClaimResponse(
        status=str(result.get("status", "")),
        old_value=result.get("old_value"),
        new_value=result.get("new_value"),
        absolute_change=result.get("absolute_change"),
        percentage_change=result.get("percentage_change"),
        source_fact_ids=source_fact_ids,
    ).model_dump(mode="json")


def build_server() -> FastMCP:
    """Build the read-only M4.3 MCP server."""

    mcp = FastMCP(
        "verified-credit-research-agent",
        instructions=(
            "Read-only MCP server for the Ford debt/liquidity M3 demo. "
            "Currently supports ticker F only."
        ),
    )

    @mcp.tool(
        name="hybrid_retrieve",
        description=(
            "Search Ford SEC filing evidence using the existing M3 hybrid retrieval pipeline. "
            "Read-only; currently supports ticker F."
        ),
    )
    def hybrid_retrieve(
        query: str,
        top_n: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return hybrid_retrieve_tool(query=query, top_n=top_n, filters=filters)

    @mcp.tool(
        name="verify_numeric_claim",
        description=(
            "Verify a Ford debt/liquidity metric using existing deterministic M3 verification. "
            "Read-only; currently supports ticker F."
        ),
    )
    def verify_numeric_claim(
        ticker: str,
        metric_name: str,
        old_year: int,
        new_year: int,
    ) -> Dict[str, Any]:
        return verify_numeric_claim_tool(
            ticker=ticker,
            metric_name=metric_name,
            old_year=old_year,
            new_year=new_year,
        )

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()

