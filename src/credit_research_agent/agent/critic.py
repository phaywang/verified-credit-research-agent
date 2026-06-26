"""Citation and support critic for Milestone 1 final answers."""

from __future__ import annotations

from typing import List, Set

from credit_research_agent.schemas import AnswerClaim, CriticReport, EvidenceChunk, FinalAnswer


def critique_answer(final_answer: FinalAnswer, evidence: List[EvidenceChunk]) -> CriticReport:
    evidence_ids: Set[str] = {chunk.chunk_id for chunk in evidence}
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

