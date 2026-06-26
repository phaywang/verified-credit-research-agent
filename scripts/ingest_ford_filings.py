"""Fetch Ford filings, parse sections, and write Milestone 1 chunks."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.config import DATA_DIR, FORD_CIK, FORD_COMPANY, FORD_TICKER
from credit_research_agent.ingestion.filing_parser import parse_sections
from credit_research_agent.ingestion.sec_fetcher import fetch_company_filing
from credit_research_agent.ingestion.section_chunker import chunk_sections


def main() -> None:
    processed_dir = DATA_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = processed_dir / "ford_2023_2025_chunks.jsonl"
    summary_path = processed_dir / "ford_2023_2025_chunk_summary.json"

    documents = [
        fetch_company_filing(FORD_COMPANY, FORD_TICKER, FORD_CIK, 2023, "10-K"),
        fetch_company_filing(FORD_COMPANY, FORD_TICKER, FORD_CIK, 2025, "10-K"),
    ]

    all_sections = []
    all_chunks = []
    for document in documents:
        sections = parse_sections(document)
        chunks = chunk_sections(sections)
        all_sections.extend(sections)
        all_chunks.extend(chunks)

    with chunk_path.open("w", encoding="utf-8") as handle:
        for chunk in all_chunks:
            handle.write(json.dumps(chunk.model_dump(mode="json"), sort_keys=True) + "\n")

    chunk_counts = Counter(
        (chunk.fiscal_year, chunk.filing_type, chunk.section_type, chunk.section_name)
        for chunk in all_chunks
    )
    summary = {
        "documents": [document.model_dump(mode="json") for document in documents],
        "section_count": len(all_sections),
        "chunk_count": len(all_chunks),
        "chunk_counts": [
            {
                "fiscal_year": fiscal_year,
                "filing_type": filing_type,
                "section_type": section_type,
                "section_name": section_name,
                "chunk_count": count,
            }
            for (fiscal_year, filing_type, section_type, section_name), count in sorted(
                chunk_counts.items()
            )
        ],
        "chunk_path": str(chunk_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {len(all_chunks)} chunks to {chunk_path}")
    print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()

