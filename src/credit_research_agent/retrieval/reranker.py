"""Local fallback reranker for Milestone 1."""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np

from credit_research_agent.retrieval.dense_embedder import DenseEmbedder
from credit_research_agent.retrieval.text import searchable_text
from credit_research_agent.schemas import Citation, EvidenceChunk, RetrievalResult


SECTION_BOOSTS = {
    "liquidity": 0.14,
    "debt": 0.14,
    "credit_facilities": 0.13,
    "risk_factors": 0.02,
    "mda": -0.02,
}

TITLE_BOOSTS = {
    "liquidity and capital resources": 0.03,
    "debt and commitments": 0.03,
    "total debt maturities": 0.04,
    "committed credit facilities": 0.03,
    "other unsecured credit facilities": 0.025,
}

CONTENT_BOOSTS = {
    "carrying value of company debt": 0.08,
    "debt payable within one year": 0.08,
    "long-term debt payable": 0.06,
    "total debt maturities": 0.08,
    "company debt excluding ford credit": 0.04,
    "company liquidity": 0.04,
    "net liquidity available for use": 0.04,
    "committed capacity totaled": 0.04,
    "remains well capitalized": 0.06,
    "funding diversified across platforms": 0.06,
    "we expect": 0.04,
    "primarily due to": 0.04,
    "driven by": 0.04,
}

CONTENT_PENALTIES = {
    "derivative financial instruments": -0.08,
    "hedging activities": -0.05,
    "special purpose entities": -0.04,
}


class Reranker:
    """Rerank hybrid candidates using embedding cosine plus evidence-section boost."""

    def __init__(self, embedder: Optional[DenseEmbedder] = None) -> None:
        self.embedder = embedder or DenseEmbedder()

    def _normalize_score(self, raw_score: float) -> float:
        return 1.0 / (1.0 + math.exp(-raw_score))

    def _categories(self, result: RetrievalResult) -> List[str]:
        chunk = result.chunk
        if not chunk:
            return []
        categories = [chunk.section_type]
        text = chunk.text.lower()
        if any(term in text for term in ["$", "billion", "million", "%"]):
            categories.append("numeric_facts")
        if any(
            term in text
            for term in [
                "we expect",
                "we believe",
                "primarily",
                "reflecting",
                "driven by",
                "explained by",
            ]
        ):
            categories.append("management_explanation")
        return sorted(set(categories))

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        top_k: int = 10,
    ) -> List[EvidenceChunk]:
        if not candidates:
            return []

        query_embedding = self.embedder.embed_query(query)
        texts = [
            searchable_text(
                candidate.chunk.section_name if candidate.chunk else candidate.section_name,
                candidate.chunk.section_type if candidate.chunk else "",
                candidate.text,
            )
            for candidate in candidates
        ]
        embeddings = self.embedder.embed_texts(texts)
        cosine_scores = embeddings @ query_embedding.astype(np.float32)

        scored = []
        for candidate, cosine_score in zip(candidates, cosine_scores):
            section_type = candidate.chunk.section_type if candidate.chunk else ""
            section_name = candidate.chunk.section_name.lower() if candidate.chunk else ""
            section_boost = SECTION_BOOSTS.get(section_type, 0.0)
            title_boost = sum(
                boost
                for title, boost in TITLE_BOOSTS.items()
                if title in section_name
            )
            text_lower = candidate.text.lower()
            content_boost = sum(
                boost
                for phrase, boost in CONTENT_BOOSTS.items()
                if phrase in text_lower
            )
            content_penalty = sum(
                penalty
                for phrase, penalty in CONTENT_PENALTIES.items()
                if phrase in text_lower
            )
            rrf_component = min(candidate.rrf_score * 2.0, 0.06)
            reranker_score = float(
                cosine_score
                + section_boost
                + title_boost
                + content_boost
                + content_penalty
                + rrf_component
            )
            scored.append((candidate, reranker_score))
        scored.sort(key=lambda item: item[1], reverse=True)

        evidence: List[EvidenceChunk] = []
        for candidate, score in scored[:top_k]:
            if not candidate.chunk:
                continue
            chunk = candidate.chunk
            evidence.append(
                EvidenceChunk(
                    chunk_id=chunk.chunk_id,
                    fiscal_year=chunk.fiscal_year,
                    filing_type=chunk.filing_type,
                    section_name=chunk.section_name,
                    section_type=chunk.section_type,
                    reranker_score=self._normalize_score(score),
                    rrf_score=candidate.rrf_score,
                    evidence_category=self._categories(candidate),
                    text=chunk.text,
                    citation=Citation(
                        source_url=chunk.source_url,
                        filing_date=chunk.filing_date,
                        accession_number=chunk.accession_number,
                        chunk_id=chunk.chunk_id,
                    ),
                )
            )
        return evidence
