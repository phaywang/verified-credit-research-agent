"""Section-aware chunking for SEC filing text."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import DefaultDict, Iterable, List

from credit_research_agent.schemas import FilingChunk, FilingSection


SECTION_SLUGS = {
    "liquidity": "liquidity",
    "debt": "debt",
    "risk_factors": "risk_factors",
    "mda": "mda",
    "credit_facilities": "credit_facilities",
    "cash_flow": "cash_flow",
    "full_filing": "full_filing",
}


def _tokenize(text: str) -> List[str]:
    return text.split()


def _detokenize(tokens: List[str]) -> str:
    return " ".join(tokens)


def _chunk_tokens(
    tokens: List[str],
    max_tokens: int,
    overlap_tokens: int,
) -> Iterable[tuple[int, int, str]]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be non-negative and smaller than max_tokens")

    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        yield start, end, _detokenize(tokens[start:end])
        if end == len(tokens):
            break
        start = end - overlap_tokens


def _section_slug(section_type: str) -> str:
    return SECTION_SLUGS.get(section_type, re.sub(r"[^a-z0-9]+", "_", section_type.lower()).strip("_"))


def chunk_sections(
    sections: List[FilingSection],
    max_tokens: int = 650,
    overlap_tokens: int = 80,
) -> List[FilingChunk]:
    """Create section-aware chunks while preserving filing metadata."""

    chunks: List[FilingChunk] = []
    counters: DefaultDict[tuple[str, int, str, str], int] = defaultdict(int)
    for section in sections:
        document = section.document
        tokens = _tokenize(section.text)
        if not tokens:
            continue
        slug = _section_slug(section.section_type)
        counter_key = (
            document.ticker,
            document.fiscal_year,
            document.filing_type,
            slug,
        )
        for _start, _end, text in _chunk_tokens(tokens, max_tokens, overlap_tokens):
            counters[counter_key] += 1
            chunk_id = (
                f"{document.ticker}_{document.fiscal_year}_"
                f"{document.filing_type.replace('-', '')}_{slug}_"
                f"{counters[counter_key]:03d}"
            )
            chunks.append(
                FilingChunk(
                    company=document.company,
                    ticker=document.ticker,
                    cik=document.cik,
                    fiscal_year=document.fiscal_year,
                    filing_type=document.filing_type,
                    section_name=section.section_name,
                    section_type=section.section_type,
                    chunk_id=chunk_id,
                    text=text,
                    source_url=document.source_url,
                    filing_date=document.filing_date,
                    accession_number=document.accession_number,
                    char_start=section.char_start,
                    char_end=section.char_end,
                )
            )
    return chunks

