"""Heading-based SEC filing section parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from credit_research_agent.schemas import FilingDocument, FilingSection


MIN_SECTION_CHARS = 500
SHORT_EVIDENCE_SECTION_CHARS = 180


@dataclass(frozen=True)
class HeadingMarker:
    line_index: int
    section_name: str
    section_type: str


def html_to_text(html: str) -> str:
    """Convert SEC HTML to normalized plain text while preserving line breaks."""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(
        lambda item: item.name
        and (
            item.name.lower() in {"ix:hidden", "ix:header", "ix:references", "ix:resources"}
            or item.get("style", "").lower().find("display:none") >= 0
            or item.get("style", "").lower().find("display: none") >= 0
            or item.get("hidden") is not None
        )
    ):
        tag.decompose()
    raw_text = soup.get_text("\n")
    normalized = normalize_text(raw_text)
    lines = normalized.splitlines()
    for idx, line in enumerate(lines):
        if "UNITED STATES SECURITIES AND EXCHANGE COMMISSION" in line.upper():
            return "\n".join(lines[idx:])
    return normalized


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _canonical(line: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()


def _classify_heading(line: str) -> Optional[tuple[str, str]]:
    canonical = _canonical(line)
    if not canonical or len(canonical) > 140:
        return None
    if canonical.startswith("day revolving credit facility"):
        return None

    if re.match(r"note \d+ debt and commitments", canonical):
        return "Debt and Commitments", "debt"
    if re.match(r"item 7a ", canonical):
        return line, "boundary"
    if re.match(r"item 1a risk factors$", canonical) or canonical == "risk factors":
        return "Risk Factors", "risk_factors"
    if re.match(r"item 7 management s discussion", canonical):
        return "Management's Discussion and Analysis", "mda"
    if canonical in {
        "management s discussion and analysis",
        "management discussion and analysis",
    }:
        return "Management's Discussion and Analysis", "mda"
    if "liquidity and capital resources" in canonical:
        return "Liquidity and Capital Resources", "liquidity"
    if canonical in {"debt", "long term debt", "debt and commitments"}:
        return line.rstrip("."), "debt"
    if canonical in {
        "credit facilities",
        "committed credit facilities",
        "other unsecured credit facilities",
    }:
        return line.rstrip("."), "credit_facilities"
    if canonical in {"cash flows", "operating activities", "financing activities"}:
        return line, "cash_flow"
    if canonical in {
        "total debt maturities",
        "memo unsecured long term debt maturities",
    }:
        return line.rstrip("."), "debt"
    if re.match(r"item \d+[a-z]?$", canonical) or re.match(r"note \d+", canonical):
        return line, "boundary"
    if canonical in {
        "credit ratings",
        "outlook",
        "cautionary note on forward looking statements",
        "non gaap financial measures that supplement gaap measures",
        "critical accounting estimates",
    }:
        return line, "boundary"
    return None


def _find_markers(lines: List[str]) -> List[HeadingMarker]:
    markers: List[HeadingMarker] = []
    seen = set()
    body_start = _body_start_index(lines)
    for idx, line in enumerate(lines[body_start:], start=body_start):
        classified = _classify_heading(line)
        if not classified:
            continue
        section_name, section_type = classified
        key = (idx, section_name, section_type)
        if key in seen:
            continue
        seen.add(key)
        markers.append(
            HeadingMarker(
                line_index=idx,
                section_name=section_name,
                section_type=section_type,
            )
        )
    return markers


def _body_start_index(lines: List[str]) -> int:
    item_1_indices = [
        idx
        for idx, line in enumerate(lines)
        if _canonical(line) in {"item 1", "item 1 business"}
    ]
    if len(item_1_indices) >= 2:
        return item_1_indices[1]
    if item_1_indices:
        return item_1_indices[0]
    return 0


def _iter_sections_from_markers(
    document: FilingDocument,
    lines: List[str],
    markers: List[HeadingMarker],
) -> Iterable[FilingSection]:
    for idx, marker in enumerate(markers):
        next_index = markers[idx + 1].line_index if idx + 1 < len(markers) else len(lines)
        section_lines = lines[marker.line_index:next_index]
        section_text = "\n".join(section_lines).strip()
        if marker.section_type == "boundary":
            continue
        min_chars = (
            SHORT_EVIDENCE_SECTION_CHARS
            if marker.section_type in {"credit_facilities", "debt"}
            else MIN_SECTION_CHARS
        )
        if len(section_text) < min_chars:
            continue
        yield FilingSection(
            document=document,
            section_name=marker.section_name,
            section_type=marker.section_type,
            text=section_text,
            char_start=None,
            char_end=None,
        )


def parse_sections(filing: FilingDocument) -> List[FilingSection]:
    """Parse target debt/liquidity related sections from a filing document."""

    html = Path(filing.local_path).read_text(encoding="utf-8", errors="ignore")
    text = html_to_text(html)
    lines = text.splitlines()
    markers = _find_markers(lines)
    sections = list(_iter_sections_from_markers(filing, lines, markers))

    if sections:
        return sections

    return [
        FilingSection(
            document=filing,
            section_name="Full Filing",
            section_type="full_filing",
            text=text,
            char_start=0,
            char_end=len(text),
        )
    ]
