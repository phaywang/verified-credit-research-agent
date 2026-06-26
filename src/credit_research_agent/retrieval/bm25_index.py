"""Small local BM25 index for Milestone 1."""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List

from credit_research_agent.retrieval.text import searchable_text, tokenize
from credit_research_agent.schemas import FilingChunk, RetrievalResult


class BM25Index:
    """Pure-Python BM25 over filing chunks."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: List[FilingChunk] = []
        self.doc_term_freqs: List[Counter[str]] = []
        self.doc_lengths: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.avg_doc_len = 0.0

    def build(self, chunks: List[FilingChunk]) -> None:
        self.chunks = chunks
        self.doc_term_freqs = []
        self.doc_lengths = []
        self.doc_freqs = {}

        for chunk in chunks:
            tokens = tokenize(
                searchable_text(chunk.section_name, chunk.section_type, chunk.text)
            )
            term_freq = Counter(tokens)
            self.doc_term_freqs.append(term_freq)
            self.doc_lengths.append(len(tokens))
            for term in term_freq:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.avg_doc_len = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )

    def _idf(self, term: str) -> float:
        n_docs = len(self.chunks)
        doc_freq = self.doc_freqs.get(term, 0)
        return math.log(1 + (n_docs - doc_freq + 0.5) / (doc_freq + 0.5))

    def _score_doc(self, query_terms: List[str], doc_idx: int) -> float:
        score = 0.0
        term_freq = self.doc_term_freqs[doc_idx]
        doc_len = self.doc_lengths[doc_idx]
        for term in query_terms:
            freq = term_freq.get(term, 0)
            if freq == 0:
                continue
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (
                1 - self.b + self.b * doc_len / max(self.avg_doc_len, 1.0)
            )
            score += self._idf(term) * numerator / denominator
        return score

    def search(self, query: str, top_n: int) -> List[RetrievalResult]:
        query_terms = tokenize(query)
        scored = [
            (idx, self._score_doc(query_terms, idx))
            for idx in range(len(self.chunks))
        ]
        scored = [item for item in scored if item[1] > 0]
        scored.sort(key=lambda item: item[1], reverse=True)

        results: List[RetrievalResult] = []
        for rank, (idx, score) in enumerate(scored[:top_n], start=1):
            chunk = self.chunks[idx]
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    query=query,
                    section_name=chunk.section_name,
                    fiscal_year=chunk.fiscal_year,
                    bm25_rank=rank,
                    bm25_score=score,
                    text=chunk.text,
                    source_url=chunk.source_url,
                    chunk=chunk,
                )
            )
        return results

