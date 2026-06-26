"""Reciprocal Rank Fusion for sparse and dense retrieval results."""

from __future__ import annotations

from typing import Dict, List

from credit_research_agent.schemas import RetrievalResult


def reciprocal_rank_fusion(
    ranked_lists: List[List[RetrievalResult]],
    k: int = 60,
) -> List[RetrievalResult]:
    by_chunk_id: Dict[str, RetrievalResult] = {}
    scores: Dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            chunk_id = result.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in by_chunk_id:
                by_chunk_id[chunk_id] = result.model_copy(deep=True)
            else:
                merged = by_chunk_id[chunk_id]
                merged.bm25_rank = merged.bm25_rank or result.bm25_rank
                merged.bm25_score = merged.bm25_score or result.bm25_score
                merged.vector_rank = merged.vector_rank or result.vector_rank
                merged.vector_score = merged.vector_score or result.vector_score

    fused = list(by_chunk_id.values())
    fused.sort(key=lambda result: scores[result.chunk_id], reverse=True)
    for rank, result in enumerate(fused, start=1):
        result.rrf_score = scores[result.chunk_id]
        result.fused_rank = rank
    return fused

