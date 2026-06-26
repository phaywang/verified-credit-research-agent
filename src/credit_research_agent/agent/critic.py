"""Citation and support critic for Milestone 1 final answers."""

from __future__ import annotations

from typing import Iterable, List, Optional, Set

from credit_research_agent.schemas import (
    AnswerClaim,
    CriticReport,
    EvidenceChunk,
    FinalAnswer,
    NumericVerificationResult,
)


def critique_answer(
    final_answer: FinalAnswer,
    evidence: List[EvidenceChunk],
    *,
    extra_allowed_chunk_ids: Optional[Iterable[str]] = None,
    verification_results: Optional[List[NumericVerificationResult]] = None,
) -> CriticReport:
    evidence_ids: Set[str] = {chunk.chunk_id for chunk in evidence}
    if extra_allowed_chunk_ids:
        evidence_ids.update(extra_allowed_chunk_ids)
    unsupported: List[AnswerClaim] = []
    notes: List[str] = []

    for claim in final_answer.claims:
        if not claim.citation_chunk_ids:
            unsupported.append(claim)
            notes.append(f"Claim has no citations: {claim.claim}")
            continue
        missing = [chunk_id for chunk_id in claim.citation_chunk_ids if chunk_id not in evidence_ids]
        if missing:
            unsupported.append(
                claim.model_copy(update={"support_status": "unsupported"})
            )
            notes.append(f"Claim cites chunks not present in evidence set: {', '.join(missing)}")

    if verification_results:
        unverified_metrics = {
            result.metric_name
            for result in verification_results
            if result.status != "verified"
        }
        for metric in unverified_metrics:
            readable = metric.replace("_", " ")
            if readable in final_answer.markdown.lower():
                notes.append(
                    f"Unverified metric appears in final answer text and requires review: {metric}"
                )

    return CriticReport(
        unsupported_claims=unsupported,
        needs_repair=bool(unsupported),
        notes=notes,
    )


def repair_answer(final_answer: FinalAnswer, critic_report: CriticReport) -> FinalAnswer:
    if not critic_report.needs_repair:
        return final_answer
    unsupported = {claim.claim for claim in critic_report.unsupported_claims}
    repaired_claims = [
        claim for claim in final_answer.claims if claim.claim not in unsupported
    ]
    markdown = final_answer.markdown + "\nUnsupported claims were removed by the citation critic.\n"
    return FinalAnswer(
        markdown=markdown,
        claims=repaired_claims,
        trace_log_path=final_answer.trace_log_path,
    )
