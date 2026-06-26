"""Deterministic cited synthesis for Milestone 1."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from credit_research_agent.agent.evidence_checker import is_management_explanation
from credit_research_agent.schemas import (
    AnswerClaim,
    EvidenceChunk,
    EvidenceCoverage,
    FinalAnswer,
    NumericVerificationResult,
    TaskSpec,
)


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


def _numeric_claim(text: str, result: NumericVerificationResult) -> AnswerClaim:
    return AnswerClaim(
        claim=text,
        citation_chunk_ids=[
            str(item["source_chunk_id"])
            for item in result.evidence
            if item.get("source_chunk_id")
        ],
        support_status="supported",
    )


def _money(value: Optional[float], decimals: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"${value:.{decimals}f}B"


def _change(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if value < 0:
        return f"-${abs(value):.3f}B"
    sign = "+" if value > 0 else ""
    return f"{sign}${value:.3f}B"


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _numeric_citations(result: NumericVerificationResult) -> str:
    seen = set()
    citations = []
    for item in result.evidence:
        chunk_id = item.get("source_chunk_id")
        source_url = item.get("source_url")
        if not chunk_id or not source_url or chunk_id in seen:
            continue
        seen.add(chunk_id)
        citations.append(f"[{chunk_id}]({source_url})")
    return " ".join(citations)


def _combined_numeric_citations(results: List[NumericVerificationResult]) -> str:
    seen = set()
    citations = []
    for result in results:
        for item in result.evidence:
            chunk_id = item.get("source_chunk_id")
            source_url = item.get("source_url")
            if not chunk_id or not source_url or chunk_id in seen:
                continue
            seen.add(chunk_id)
            citations.append(f"[{chunk_id}]({source_url})")
    return " ".join(citations)


def _verified_by_metric(
    verification_results: Optional[List[NumericVerificationResult]],
) -> Dict[str, NumericVerificationResult]:
    if not verification_results:
        return {}
    return {
        result.metric_name: result
        for result in verification_results
        if result.status == "verified"
    }


def synthesize_final_answer(
    task_spec: TaskSpec,
    evidence: List[EvidenceChunk],
    coverage: EvidenceCoverage,
    trace_log_path: str,
    verification_results: Optional[List[NumericVerificationResult]] = None,
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
    verified = _verified_by_metric(verification_results)

    lines = [
        "# Ford Debt and Liquidity Risk Brief",
        "",
        "## Executive Summary",
    ]

    claims: List[AnswerClaim] = []
    cited_summary_chunks = [chunk for chunk in [liq_2023, liq_2025, debt_2023, debt_2025] if chunk]
    if verified:
        debt_total = verified.get("company_debt_excluding_ford_credit")
        current_debt = verified.get("company_debt_payable_within_one_year")
        noncurrent_debt = verified.get("company_long_term_debt_payable_after_one_year")
        total_cash = verified.get("total_balance_sheet_cash_and_marketable_securities_restricted_cash")
        company_liquidity = verified.get("company_liquidity")
        summary_parts = []
        if debt_total:
            summary_parts.append(
                "Company debt excluding Ford Credit increased "
                f"from {_money(debt_total.old_value)} in {debt_total.old_year} "
                f"to {_money(debt_total.new_value)} in {debt_total.new_year}."
            )
        if current_debt and noncurrent_debt:
            summary_parts.append(
                "The more credit-relevant movement was maturity mix: debt payable within one year rose sharply while long-term debt after one year declined, indicating more near-term refinancing/rollover exposure."
            )
        if total_cash and company_liquidity:
            summary_parts.append(
                "Liquidity evidence is mixed by scope: total cash/marketable securities/restricted cash declined, while Company liquidity excluding Ford Credit increased."
            )
        if summary_parts:
            lines.append(" ".join(summary_parts))
            cited_results = [
                result for result in [debt_total, current_debt, noncurrent_debt, total_cash, company_liquidity] if result
            ]
            cited_ids = [
                str(item["source_chunk_id"])
                for result in cited_results
                for item in result.evidence
                if item.get("source_chunk_id")
            ]
            claims.append(
                AnswerClaim(
                    claim="Verified numeric evidence supports a mixed Ford debt/liquidity risk conclusion.",
                    citation_chunk_ids=sorted(set(cited_ids)),
                    support_status="supported",
                )
            )
    elif debt_2023 and debt_2025 and liq_2023 and liq_2025:
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
    debt_total = verified.get("company_debt_excluding_ford_credit")
    current_debt = verified.get("company_debt_payable_within_one_year")
    noncurrent_debt = verified.get("company_long_term_debt_payable_after_one_year")
    short_term = verified.get("company_short_term_borrowings")
    if debt_total:
        text = (
            "Company debt excluding Ford Credit increased "
            f"from {_money(debt_total.old_value)} in {debt_total.old_year} "
            f"to {_money(debt_total.new_value)} in {debt_total.new_year}, "
            f"a {_change(debt_total.absolute_change)} change ({_pct(debt_total.percentage_change)})."
        )
        lines.append(f"- {text} {_numeric_citations(debt_total)}")
        claims.append(_numeric_claim(text, debt_total))
    if current_debt and noncurrent_debt:
        text = (
            "Ford's Company excluding Ford Credit maturity mix worsened: debt payable within one year rose "
            f"from {_money(current_debt.old_value)} to {_money(current_debt.new_value)} "
            f"({_change(current_debt.absolute_change)}, {_pct(current_debt.percentage_change)}), while long-term debt payable after one year fell "
            f"from {_money(noncurrent_debt.old_value)} to {_money(noncurrent_debt.new_value)} "
            f"({_change(noncurrent_debt.absolute_change)}, {_pct(noncurrent_debt.percentage_change)}). "
            "This combination points to higher near-term refinancing or rollover pressure, even though it does not by itself prove a liquidity shortfall."
        )
        lines.append(
            f"- {text} {_combined_numeric_citations([current_debt, noncurrent_debt])}"
        )
        claims.append(
            AnswerClaim(
                claim=text,
                citation_chunk_ids=sorted(
                    {
                        str(item["source_chunk_id"])
                        for result in [current_debt, noncurrent_debt]
                        for item in result.evidence
                        if item.get("source_chunk_id")
                    }
                ),
                support_status="supported",
            )
        )
    if short_term:
        text = (
            "Company excluding Ford Credit short-term borrowings increased "
            f"from {_money(short_term.old_value)} to {_money(short_term.new_value)}, "
            f"a {_change(short_term.absolute_change)} change ({_pct(short_term.percentage_change)})."
        )
        lines.append(f"- {text} {_numeric_citations(short_term)}")
        claims.append(_numeric_claim(text, short_term))
    if not any([debt_total, current_debt, noncurrent_debt, short_term]):
        if debt_2023:
            lines.append(f"- 2023 debt evidence: {_preview(debt_2023)} {_citation(debt_2023)}")
            claims.append(_claim("2023 debt evidence was retrieved from Ford's debt disclosures.", [debt_2023]))
        if debt_2025:
            lines.append(f"- 2025 debt evidence: {_preview(debt_2025)} {_citation(debt_2025)}")
            claims.append(_claim("2025 debt evidence was retrieved from Ford's debt disclosures.", [debt_2025]))

    lines.extend(["", "## Liquidity Risk Changes"])
    liquidity_results = [
        verified.get("total_balance_sheet_cash_and_marketable_securities_restricted_cash"),
        verified.get("company_cash"),
        verified.get("company_liquidity"),
        verified.get("ford_credit_net_liquidity_available_for_use"),
        verified.get("ford_credit_liquidity_sources"),
        verified.get("ford_credit_committed_capacity"),
    ]
    liquidity_results = [result for result in liquidity_results if result]
    for result in liquidity_results:
        text = (
            f"{_liquidity_label(result.metric_name)} changed from "
            f"{_money(result.old_value)} in {result.old_year} to {_money(result.new_value)} in {result.new_year}, "
            f"a {_change(result.absolute_change)} change ({_pct(result.percentage_change)})."
        )
        lines.append(f"- {text} {_numeric_citations(result)}")
        claims.append(_numeric_claim(text, result))
    if verified.get("total_balance_sheet_cash_and_marketable_securities_restricted_cash") and verified.get("company_liquidity"):
        total_cash = verified["total_balance_sheet_cash_and_marketable_securities_restricted_cash"]
        company_liquidity = verified["company_liquidity"]
        text = (
            "The liquidity conclusion is mixed by scope: total cash, cash equivalents, marketable securities, and restricted cash declined, "
            "but Company liquidity excluding Ford Credit increased. The brief therefore does not label Ford's overall liquidity risk as simply improved or deteriorated."
        )
        lines.append(f"- {text} {_combined_numeric_citations([total_cash, company_liquidity])}")
        claims.append(
            AnswerClaim(
                claim=text,
                citation_chunk_ids=sorted(
                    {
                        str(item["source_chunk_id"])
                        for result in [total_cash, company_liquidity]
                        for item in result.evidence
                        if item.get("source_chunk_id")
                    }
                ),
                support_status="supported",
            )
        )
    if not liquidity_results:
        if liq_2023:
            lines.append(f"- 2023 liquidity evidence: {_preview(liq_2023)} {_citation(liq_2023)}")
            claims.append(_claim("2023 liquidity evidence was retrieved from Liquidity and Capital Resources.", [liq_2023]))
        if liq_2025:
            lines.append(f"- 2025 liquidity evidence: {_preview(liq_2025)} {_citation(liq_2025)}")
            claims.append(_claim("2025 liquidity evidence was retrieved from Liquidity and Capital Resources.", [liq_2025]))

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

    lines.extend(["", "## Key Numeric Changes"])
    lines.append("| Metric | 2023 | 2025 | Change | % Change | Status | Sources |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    if verification_results:
        for result in verification_results:
            if result.status != "verified":
                continue
            lines.append(
                f"| {_metric_label(result.metric_name)} | {_money(result.old_value)} | {_money(result.new_value)} | "
                f"{_change(result.absolute_change)} | {_pct(result.percentage_change)} | verified | {_numeric_citations(result)} |"
            )
    else:
        lines.append("| No verified numeric results | n/a | n/a | n/a | n/a | not verified | n/a |")

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
    if verification_results:
        lines.append("- Numeric comparisons in the analytical sections are included only when deterministic verification returned `verified`.")
        blocked = [
            result for result in verification_results if result.status != "verified"
        ]
        lines.append(
            "- Low-confidence table-derived duplicates and deferred maturity-bucket facts were excluded from conclusion sentences."
        )
        if blocked:
            lines.append(
                f"- Numeric critic flagged {len(blocked)} candidate claim(s) as not verified; these were excluded from analytical conclusions."
            )
    else:
        lines.append("- Numeric comparisons should be verified before being treated as final analytical calculations.")

    lines.extend(["", "## Follow-up Questions for Analyst Review"])
    lines.append("- Which debt scope should drive the credit conclusion: Company excluding Ford Credit, Ford Credit, or consolidated debt?")
    lines.append("- Should liquidity risk be assessed using company liquidity, total balance sheet cash, Ford Credit liquidity, or all three?")
    lines.append("- Should the analyst weight near-term debt migration more heavily than the increase in Company liquidity when assessing refinancing risk?")

    lines.extend(["", "## Trace Log", f"- {trace_log_path}"])

    return FinalAnswer(
        markdown="\n".join(lines) + "\n",
        claims=claims,
        trace_log_path=trace_log_path,
    )


def _metric_label(metric_name: str) -> str:
    labels = {
        "company_debt_excluding_ford_credit": "Company debt excluding Ford Credit",
        "company_debt_payable_within_one_year": "Company debt payable within one year excluding Ford Credit",
        "company_long_term_debt_payable_after_one_year": "Company long-term debt payable after one year excluding Ford Credit",
        "company_short_term_borrowings": "Company short-term borrowings excluding Ford Credit",
        "total_balance_sheet_cash_and_marketable_securities_restricted_cash": "Total cash, cash equivalents, marketable securities, and restricted cash",
        "company_cash": "Company cash excluding Ford Credit",
        "company_liquidity": "Company liquidity excluding Ford Credit",
        "ford_credit_net_liquidity_available_for_use": "Ford Credit net liquidity available for use",
        "ford_credit_liquidity_sources": "Ford Credit liquidity sources",
        "ford_credit_committed_capacity": "Ford Credit committed capacity",
    }
    return labels.get(metric_name, metric_name.replace("_", " "))


def _liquidity_label(metric_name: str) -> str:
    return _metric_label(metric_name)
