"""Run hybrid retrieval + rerank sanity check for the Ford demo."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.config import DATA_DIR
from credit_research_agent.retrieval.chunk_store import load_chunks_jsonl
from credit_research_agent.retrieval.hybrid_retriever import HybridRetriever
from credit_research_agent.retrieval.reranker import Reranker


INITIAL_QUERY = (
    "Ford 2023 2025 10-K debt liquidity risk long-term debt liquidity "
    "capital resources credit facilities management discussion"
)


def main() -> None:
    chunk_path = DATA_DIR / "processed" / "ford_2023_2025_chunks.jsonl"
    chunks = load_chunks_jsonl(chunk_path)
    retriever = HybridRetriever(chunks)
    candidates = retriever.retrieve(INITIAL_QUERY, top_n=30)
    evidence = Reranker(retriever.embedder).rerank(INITIAL_QUERY, candidates, top_k=10)

    print(f"query: {INITIAL_QUERY}")
    print("rank | chunk_id | section_type | section_name | year | rrf_score | reranker_score")
    for idx, chunk in enumerate(evidence, start=1):
        print(
            f"{idx:>4} | {chunk.chunk_id} | {chunk.section_type} | "
            f"{chunk.section_name} | {chunk.fiscal_year} | "
            f"{chunk.rrf_score:.6f} | {chunk.reranker_score:.6f}"
        )
        preview = " ".join(chunk.text.split())[:220]
        print(f"     {preview}")


if __name__ == "__main__":
    main()

