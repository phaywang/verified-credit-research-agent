"""Numpy brute-force cosine vector search."""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from credit_research_agent.schemas import FilingChunk, RetrievalResult


class VectorIndex:
    """Brute-force cosine search over normalized embedding vectors."""

    def __init__(self) -> None:
        self.chunks: List[FilingChunk] = []
        self.embeddings: Optional[np.ndarray] = None

    def build(self, chunks: List[FilingChunk], embeddings: np.ndarray) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)

    def search(
        self,
        query: str,
        query_embedding: np.ndarray,
        top_n: int,
    ) -> List[RetrievalResult]:
        if self.embeddings is None:
            raise ValueError("VectorIndex must be built before search")
        if not len(self.chunks):
            return []

        scores = self.embeddings @ query_embedding.astype(np.float32)
        ranked_indices = np.argsort(scores)[::-1][:top_n]
        results: List[RetrievalResult] = []
        for rank, idx in enumerate(ranked_indices, start=1):
            chunk = self.chunks[int(idx)]
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    query=query,
                    section_name=chunk.section_name,
                    fiscal_year=chunk.fiscal_year,
                    vector_rank=rank,
                    vector_score=float(scores[int(idx)]),
                    text=chunk.text,
                    source_url=chunk.source_url,
                    chunk=chunk,
                )
            )
        return results
