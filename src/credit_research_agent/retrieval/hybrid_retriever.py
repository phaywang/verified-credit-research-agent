"""Hybrid BM25 + dense vector retriever."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from credit_research_agent.retrieval.bm25_index import BM25Index
from credit_research_agent.retrieval.dense_embedder import DenseEmbedder
from credit_research_agent.retrieval.rrf import reciprocal_rank_fusion
from credit_research_agent.retrieval.text import searchable_text
from credit_research_agent.retrieval.vector_index import VectorIndex
from credit_research_agent.schemas import FilingChunk, RetrievalResult


@dataclass(frozen=True)
class RetrievalFilters:
    years: Optional[List[int]] = None
    filing_types: Optional[List[str]] = None


class HybridRetriever:
    def __init__(
        self,
        chunks: List[FilingChunk],
        embedder: Optional[DenseEmbedder] = None,
        rrf_k: int = 60,
    ) -> None:
        self.chunks = chunks
        self.embedder = embedder or DenseEmbedder()
        self.rrf_k = rrf_k
        self.bm25 = BM25Index()
        self.vector_index = VectorIndex()
        self.embeddings: Optional[np.ndarray] = None
        self.build()

    def _apply_filters(
        self,
        chunks: List[FilingChunk],
        filters: Optional[RetrievalFilters],
    ) -> List[FilingChunk]:
        if not filters:
            return chunks
        result = chunks
        if filters.years is not None:
            result = [chunk for chunk in result if chunk.fiscal_year in filters.years]
        if filters.filing_types is not None:
            result = [
                chunk for chunk in result if chunk.filing_type in filters.filing_types
            ]
        return result

    def build(self) -> None:
        self.bm25.build(self.chunks)
        texts = [
            searchable_text(chunk.section_name, chunk.section_type, chunk.text)
            for chunk in self.chunks
        ]
        self.embeddings = self.embedder.embed_texts(texts)
        self.vector_index.build(self.chunks, self.embeddings)

    def retrieve(
        self,
        query: str,
        top_n: int = 30,
        filters: Optional[RetrievalFilters] = None,
    ) -> List[RetrievalResult]:
        if filters:
            filtered_chunks = self._apply_filters(self.chunks, filters)
            scoped = HybridRetriever(
                filtered_chunks,
                embedder=self.embedder,
                rrf_k=self.rrf_k,
            )
            return scoped.retrieve(query, top_n=top_n)

        bm25_results = self.bm25.search(query, top_n=top_n)
        query_embedding = self.embedder.embed_query(query)
        vector_results = self.vector_index.search(query, query_embedding, top_n=top_n)
        return reciprocal_rank_fusion(
            [bm25_results, vector_results],
            k=self.rrf_k,
        )[:top_n]
