"""Deterministic cited synthesis for Milestone 1."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from credit_research_agent.agent.evidence_checker import is_management_explanation
from credit_research_agent.schemas import AnswerClaim, EvidenceChunk, EvidenceCoverage, FinalAnswer, TaskSpec


def _citation(chunk: EvidenceChunk) -> str:
    return f"[{chunk.chunk_id}]({chunk.citation.source_url})"


def _preview(chunk: EvidenceChunk, max_chars: int = 260) -> str:
    text = " ".join(chunk.text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _first(
    evidence: Iterable[EvidenceChunk],
    year: Optional[int] = None,
    section_types: Optional[set[str]] = None,
    contains: Optional[List[str]] = None,
) -> Optional[EvidenceChunk]:
    for chunk in evidence:
        if year is not None and chunk.fiscal_year != year:
            continue
        if section_types is not None and chunk.section_type not in section_types:
            continue
        if contains:
            lower = chunk.text.lower()
            if not any(term in lower for term in contains):
                continue
        return chunk
    return None


def _claim(text: str, chunks: List[EvidenceChunk]) -> AnswerClaim:
    return AnswerClaim(
        claim=text,
        citation_chunk_ids=[chunk.chunk_id for chunk in chunks],
        support_status="supported",
    )


def synthesize_final_answer(
    task_spec: TaskSpec,
    evidence: List[EvidenceChunk],
    coverage: EvidenceCoverage,
    trace_log_path: str,
) -> FinalAnswer:
    """Create a concise cited credit research brief from selected evidence."""

    evidence = sorted(
        evidence,
        key=lambda chunk: (
            chunk.fiscal_year,
            {"liquidity": 0, "credit_facilities": 1, "debt": 2, "mda": 3}.get(
                chunk.section_type, 9
            ),
            -chunk.reranker_score,
        ),
    )
    by_year: Dict[int, List[EvidenceChunk]] = defaultdict(list)
    for chunk in evidence:
        by_year[chunk.fiscal_year].append(chunk)

    liq_2023 = _first(evidence, 2023, {"liquidity"})
    liq_2025 = _first(evidence, 2025, {"liquidity"})
    debt_2023 = _first(evidence, 2023, {"debt"}, ["company debt", "debt payable", "note 19", "debt."])
    debt_2025 = _first(evidence, 2025, {"debt"}, ["company debt", "debt payable", "note 18", "debt."])
    credit_2023 = _first(evidence, 2023, {"credit_facilities"})
    credit_2025 = _first(evidence, 2025, {"credit_facilities"})
    management_chunks = [
        chunk for chunk in evidence if is_management_explanation(chunk)
    ]
    management_2023 = _first(
        management_chunks,
        2023,
        {"mda"},
        ["we manage", "we expect", "primarily due to", "driven by", "reflecting", "explained by", "remains well capitalized"],
    )
    management_2025 = _first(
        management_chunks,
        2025,
        {"mda"},
        ["we manage", "we expect", "primarily due to", "driven by", "reflecting", "explained by", "remains well capitalized"],
    )

    lines = [
        "# Ford Debt and Liquidity Risk Brief",
        "",
        "## Executive Summary",
    ]

    claims: List[AnswerClaim] = []
    cited_summary_chunks = [chunk for chunk in [liq_2023, liq_2025, debt_2023, debt_2025] if chunk]
    if debt_2023 and debt_2025 and liq_2023 and liq_2025:
        lines.append(
            "Ford's filings provide evidence for both years on liquidity resources and debt exposure, "
            "including Liquidity and Capital Resources disclosures and Debt and Commitments note disclosures. "
            + " ".join(_citation(chunk) for chunk in [liq_2023, liq_2025, debt_2023, debt_2025])
        )
        claims.append(
            _claim(
                "Ford filings provide both-year evidence on liquidity resources and debt exposure.",
                [liq_2023, liq_2025, debt_2023, debt_2025],
            )
        )
    elif cited_summary_chunks:
        lines.append(
            "The retrieved evidence covers part of the debt/liquidity question, but some comparison evidence remains limited. "
            + " ".join(_citation(chunk) for chunk in cited_summary_chunks)
        )
        claims.append(
            _claim(
                "The retrieved evidence covers part of the Ford debt/liquidity question.",
                cited_summary_chunks,
            )
        )
    else:
        lines.append(
            "The retrieved evidence is incomplete, so the brief should be read with the limitations below."
        )

    lines.extend(["", "## Debt Risk Changes"])
    if debt_2023:
        lines.append(
            f"- 2023 debt evidence: {_preview(debt_2023)} {_citation(debt_2023)}"
        )
        claims.append(_claim("2023 debt evidence was retrieved from Ford's debt disclosures.", [debt_2023]))
    if debt_2025:
        lines.append(
            f"- 2025 debt evidence: {_preview(debt_2025)} {_citation(debt_2025)}"
        )
        claims.append(_claim("2025 debt evidence was retrieved from Ford's debt disclosures.", [debt_2025]))

    lines.extend(["", "## Liquidity Risk Changes"])
    if liq_2023:
        lines.append(
            f"- 2023 liquidity evidence: {_preview(liq_2023)} {_citation(liq_2023)}"
        )
        claims.append(_claim("2023 liquidity evidence was retrieved from Liquidity and Capital Resources.", [liq_2023]))
    if liq_2025:
        lines.append(
            f"- 2025 liquidity evidence: {_preview(liq_2025)} {_citation(liq_2025)}"
        )
        claims.append(_claim("2025 liquidity evidence was retrieved from Liquidity and Capital Resources.", [liq_2025]))
    if credit_2023:
        lines.append(
            f"- 2023 credit facility evidence: {_preview(credit_2023)} {_citation(credit_2023)}"
        )
        claims.append(_claim("2023 credit facility evidence was retrieved.", [credit_2023]))
    if credit_2025:
        lines.append(
            f"- 2025 credit facility evidence: {_preview(credit_2025)} {_citation(credit_2025)}"
        )
        claims.append(_claim("2025 credit facility evidence was retrieved.", [credit_2025]))

    lines.extend(["", "## Management Explanation From Filings"])
    displayed_management = [
        chunk for chunk in [management_2023, management_2025] if chunk is not None
    ]
    if displayed_management:
        for chunk in displayed_management:
            lines.append(
                f"- {chunk.fiscal_year} management discussion: {_preview(chunk)} {_citation(chunk)}"
            )
        claims.append(
            _claim("Management explanation evidence was retrieved.", displayed_management)
        )
    else:
        lines.append("- Management explanation coverage was not fully satisfied by retrieved evidence.")

    lines.extend(["", "## Key Numeric Evidence Observed"])
    numeric_chunks = [
        chunk
        for chunk in [liq_2023, liq_2025, debt_2023, debt_2025, credit_2023, credit_2025]
        if chunk
    ]
    for chunk in numeric_chunks:
        lines.append(f"- {chunk.fiscal_year} / {chunk.section_name}: {_preview(chunk, 180)} {_citation(chunk)}")
    lines.append(
        "- Milestone 1 cites numeric disclosures but does not perform deterministic numeric verification or derived calculations."
    )

    lines.extend(["", "## Evidence Table", "| Chunk | Year | Section | Reranker | Evidence |", "|---|---:|---|---:|---|"])
    for chunk in evidence[:12]:
        lines.append(
            f"| {chunk.chunk_id} | {chunk.fiscal_year} | {chunk.section_name} | "
            f"{chunk.reranker_score:.3f} | {_preview(chunk, 140)} |"
        )

    lines.extend(["", "## Confidence and Limitations"])
    if coverage.decision == "sufficient":
        lines.append(
            "- Confidence: moderate for retrieval coverage because both years, debt, liquidity, management explanation, and numeric evidence were represented."
        )
    else:
        lines.append(
            f"- Confidence: limited because evidence coverage decision was `{coverage.decision}` and missing fields were: {', '.join(coverage.missing)}."
        )
    lines.append("- Numeric comparisons should be verified in Milestone 2 before being treated as final analytical calculations.")

    lines.extend(["", "## Follow-up Questions for Analyst Review"])
    lines.append("- Which debt scope should drive the credit conclusion: Company excluding Ford Credit, Ford Credit, or consolidated debt?")
    lines.append("- Should liquidity risk be assessed using company liquidity, total balance sheet cash, Ford Credit liquidity, or all three?")
    lines.append("- Which numeric claims should be promoted to verified claims in Milestone 2?")

    lines.extend(["", "## Trace Log", f"- {trace_log_path}"])

    return FinalAnswer(
        markdown="\n".join(lines) + "\n",
        claims=claims,
        trace_log_path=trace_log_path,
    )
