"""Numeric fact extraction for the Ford M2a demo."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from credit_research_agent.schemas import FilingChunk, NumericFact


DEBT_XBRL_CONCEPT_CANDIDATES: Dict[str, List[str]] = {
    "company_debt_excluding_ford_credit": [
        "DebtLongtermAndShorttermCombinedAmountCompanyExcludingFordCredit",
        "DebtAndCapitalLeaseObligationsOperatingSegmentsCompanyExcludingFordCredit",
        "DebtLongtermAndShorttermCombinedAmountOperatingSegmentsCompanyExcludingFordCredit",
    ],
    "company_debt_payable_within_one_year": [
        "LongTermDebtCurrentCompanyExcludingFordCredit",
        "LongTermDebtCurrentOperatingSegmentsCompanyExcludingFordCredit",
    ],
    "company_long_term_debt_payable_after_one_year": [
        "LongTermDebtNoncurrentCompanyExcludingFordCredit",
        "LongTermDebtAndCapitalLeaseObligationsCompanyExcludingFordCredit",
        "LongTermDebtNoncurrentOperatingSegmentsCompanyExcludingFordCredit",
    ],
    "company_short_term_borrowings": [
        "ShortTermBorrowingsCompanyExcludingFordCredit",
        "ShortTermBorrowingsOperatingSegmentsCompanyExcludingFordCredit",
    ],
}


DISPLAY_NAMES = {
    "company_debt_excluding_ford_credit": "Company debt excluding Ford Credit",
    "company_debt_payable_within_one_year": "Company debt payable within one year excluding Ford Credit",
    "company_long_term_debt_payable_after_one_year": "Company long-term debt payable after one year excluding Ford Credit",
    "company_short_term_borrowings": "Company short-term borrowings excluding Ford Credit",
    "company_debt_maturities_next_twelve_months": "Company debt maturities in next twelve months excluding Ford Credit",
    "total_balance_sheet_cash_and_marketable_securities_restricted_cash": "Total cash, cash equivalents, marketable securities, and restricted cash",
    "company_cash": "Company cash excluding Ford Credit",
    "company_liquidity": "Company liquidity excluding Ford Credit",
    "ford_credit_net_liquidity_available_for_use": "Ford Credit net liquidity available for use",
    "ford_credit_liquidity_sources": "Ford Credit liquidity sources",
    "ford_credit_committed_capacity": "Ford Credit committed capacity",
}


@dataclass(frozen=True)
class InlineXbrlFact:
    concept: str
    value: Optional[float]
    year: Optional[int]
    context_ref: str
    unit_ref: Optional[str]
    decimals: Optional[str]
    scale: int
    dimensions: dict[str, str] = field(default_factory=dict)


def load_chunks(path: Path) -> List[FilingChunk]:
    return [
        FilingChunk.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def extract_numeric_facts(
    chunks: List[FilingChunk],
    raw_filing_root: Path,
    years: Iterable[int] = (2023, 2025),
) -> List[NumericFact]:
    """Extract M2a numeric facts from XBRL and selected filing chunks."""

    year_list = list(years)
    facts: List[NumericFact] = []
    facts.extend(_extract_debt_xbrl_facts(chunks, raw_filing_root, year_list))
    facts.extend(_extract_liquidity_text_facts(chunks, year_list))
    return facts


def _extract_debt_xbrl_facts(
    chunks: List[FilingChunk],
    raw_filing_root: Path,
    years: List[int],
) -> List[NumericFact]:
    facts: List[NumericFact] = []
    chunks_by_year = {year: _best_debt_chunk(chunks, year) for year in years}
    for year in years:
        metadata_path = raw_filing_root / str(year) / "filing_metadata.json"
        filing_path = raw_filing_root / str(year) / "filing.html"
        if not metadata_path.exists() or not filing_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        mapped = _build_concept_mapper_input(_extract_inline_xbrl_facts(filing_path.read_text(encoding="utf-8", errors="ignore")))
        source_chunk = chunks_by_year.get(year)
        if source_chunk is None:
            continue
        for metric_name, candidates in DEBT_XBRL_CONCEPT_CANDIDATES.items():
            selected_concept = None
            selected_value = None
            for concept in candidates:
                value_by_year = mapped.get(concept, {})
                if year in value_by_year:
                    selected_concept = concept
                    selected_value = value_by_year[year]
                    break
            if selected_concept is None or selected_value is None:
                continue
            facts.append(
                _numeric_fact(
                    metric_name=metric_name,
                    fiscal_year=year,
                    value=selected_value / 1_000_000_000,
                    source_chunk=source_chunk,
                    metadata=metadata,
                    source_text=_excerpt(source_chunk.text, _debt_excerpt_terms(metric_name)),
                    extraction_method="xbrl_candidate_mapping",
                    fact_source="xbrl",
                    confidence="high",
                    review_required=False,
                    source_detail={
                        "source_classification": "xbrl_candidate",
                        "selected_concept": selected_concept,
                        "candidate_concepts": candidates,
                        "raw_value": selected_value,
                        "raw_unit": "USD",
                    },
                )
            )
    return facts


def _extract_liquidity_text_facts(
    chunks: List[FilingChunk],
    years: List[int],
) -> List[NumericFact]:
    facts: List[NumericFact] = []
    for chunk in chunks:
        if chunk.fiscal_year not in years:
            continue
        facts.extend(_extract_company_cash_liquidity_narrative(chunk))
        if chunk.section_type == "liquidity":
            facts.extend(_extract_total_balance_sheet_cash(chunk))
            facts.extend(_extract_company_cash_liquidity_table_review_only(chunk))
        elif chunk.section_type == "credit_facilities":
            facts.extend(_extract_ford_credit_liquidity_narrative(chunk))
    return facts


def _extract_total_balance_sheet_cash(chunk: FilingChunk) -> List[NumericFact]:
    pattern = re.compile(
        rf"At December 31, {chunk.fiscal_year}, total (?:balance sheet )?cash, "
        r"cash equivalents, marketable securities, and restricted cash, .*? was \$\s*([0-9.]+) billion",
        re.I | re.S,
    )
    match = pattern.search(chunk.text)
    if not match:
        return []
    return [
        _text_fact(
            chunk,
            "total_balance_sheet_cash_and_marketable_securities_restricted_cash",
            float(match.group(1)),
            match.group(0),
            "sentence_narrative",
            "high",
            False,
        )
    ]


def _extract_company_cash_liquidity_narrative(chunk: FilingChunk) -> List[NumericFact]:
    pattern = re.compile(
        rf"At December 31, {chunk.fiscal_year}, we had Company cash of \$\s*([0-9.]+) billion and liquidity of \$\s*([0-9.]+) billion",
        re.I | re.S,
    )
    match = pattern.search(chunk.text)
    if not match:
        return []
    excerpt = match.group(0)
    return [
        _text_fact(chunk, "company_cash", float(match.group(1)), excerpt, "sentence_narrative", "high", False),
        _text_fact(chunk, "company_liquidity", float(match.group(2)), excerpt, "sentence_narrative", "high", False),
    ]


def _extract_company_cash_liquidity_table_review_only(chunk: FilingChunk) -> List[NumericFact]:
    pattern = re.compile(
        r"Balance Sheets \(\$B\)\s+Company Cash\s+\$\s*([0-9.]+)\s+\$\s*([0-9.]+)\s+Liquidity\s+([0-9.]+)\s+([0-9.]+)",
        re.I | re.S,
    )
    match = pattern.search(chunk.text)
    if not match:
        return []
    excerpt = match.group(0)
    return [
        _text_fact(chunk, "company_cash", float(match.group(2)), excerpt, "table_flattened", "low", True),
        _text_fact(chunk, "company_liquidity", float(match.group(4)), excerpt, "table_flattened", "low", True),
    ]


def _extract_ford_credit_liquidity_narrative(chunk: FilingChunk) -> List[NumericFact]:
    facts: List[NumericFact] = []
    patterns = [
        (
            "ford_credit_net_liquidity_available_for_use",
            rf"At December 31, {chunk.fiscal_year}, Ford Credit.s net liquidity available for use was \$\s*([0-9.]+) billion[^.]*\.",
        ),
        (
            "ford_credit_liquidity_sources",
            rf"At December 31, {chunk.fiscal_year}, Ford Credit.s liquidity sources, including cash, committed asset-backed facilities, and unsecured credit facilities, totaled \$\s*([0-9.]+) billion[^.]*\.",
        ),
        (
            "ford_credit_committed_capacity",
            rf"At December 31, {chunk.fiscal_year}, Ford Credit.s committed capacity totaled \$\s*([0-9.]+) billion[^.]*\.",
        ),
    ]
    normalized_text = chunk.text.replace("’", "'")
    for metric_name, pattern in patterns:
        match = re.search(pattern, normalized_text, re.I | re.S)
        if match:
            facts.append(
                _text_fact(
                    chunk,
                    metric_name,
                    float(match.group(1)),
                    match.group(0),
                    "sentence_narrative",
                    "high",
                    False,
                )
            )
    return facts


def _text_fact(
    chunk: FilingChunk,
    metric_name: str,
    value: float,
    source_text: str,
    source_classification: str,
    confidence: str,
    review_required: bool,
) -> NumericFact:
    metadata = {
        "company": chunk.company,
        "ticker": chunk.ticker,
        "filing_date": chunk.filing_date,
        "accession_number": chunk.accession_number,
        "source_url": chunk.source_url,
    }
    return _numeric_fact(
        metric_name=metric_name,
        fiscal_year=chunk.fiscal_year,
        value=value,
        source_chunk=chunk,
        metadata=metadata,
        source_text=_clean(source_text),
        extraction_method="narrative_regex" if source_classification == "sentence_narrative" else "table_regex_review_only",
        fact_source="text",
        confidence=confidence,
        review_required=review_required,
        source_detail={
            "source_classification": source_classification,
            "selected_concept": None,
            "candidate_concepts": [],
            "raw_value": value,
            "raw_unit": "USD billions",
        },
    )


def _numeric_fact(
    *,
    metric_name: str,
    fiscal_year: int,
    value: float,
    source_chunk: FilingChunk,
    metadata: Dict[str, Any],
    source_text: str,
    extraction_method: str,
    fact_source: str,
    confidence: str,
    review_required: bool,
    source_detail: Dict[str, Any],
) -> NumericFact:
    fact_id = f"ford_{fiscal_year}_{metric_name}_{fact_source}_{confidence}"
    if source_detail.get("source_classification") == "table_flattened":
        fact_id += "_review"
    return NumericFact(
        fact_id=fact_id,
        company=metadata.get("company", source_chunk.company),
        ticker=metadata.get("ticker", source_chunk.ticker),
        fiscal_year=fiscal_year,
        metric_name=metric_name,
        display_name=DISPLAY_NAMES.get(metric_name, metric_name.replace("_", " ")),
        value=round(value, 6),
        unit="USD billions",
        scale="billions",
        source_text=_clean(source_text),
        source_chunk_id=source_chunk.chunk_id,
        source_url=metadata.get("source_url", source_chunk.source_url),
        filing_date=metadata.get("filing_date", source_chunk.filing_date),
        accession_number=metadata.get("accession_number", source_chunk.accession_number),
        extraction_method=extraction_method,
        fact_source=fact_source,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        review_required=review_required,
        source_detail=source_detail,
    )


def _best_debt_chunk(chunks: List[FilingChunk], year: int) -> Optional[FilingChunk]:
    debt_chunks = [
        chunk for chunk in chunks if chunk.fiscal_year == year and chunk.section_type == "debt"
    ]
    for chunk in debt_chunks:
        if "Total Company excluding Ford Credit" in chunk.text:
            return chunk
    return debt_chunks[0] if debt_chunks else None


def _debt_excerpt_terms(metric_name: str) -> List[str]:
    return {
        "company_debt_excluding_ford_credit": ["Total Company excluding Ford Credit"],
        "company_debt_payable_within_one_year": ["Total debt payable within one year"],
        "company_long_term_debt_payable_after_one_year": ["Total long-term debt payable after one year"],
        "company_short_term_borrowings": ["Short-term"],
        "company_debt_maturities_next_twelve_months": ["Total Debt Maturities", "next twelve months"],
    }.get(metric_name, ["Debt"])


def _excerpt(text: str, terms: List[str], max_chars: int = 420) -> str:
    clean = _clean(text)
    lower = clean.lower()
    for term in terms:
        idx = lower.find(term.lower())
        if idx >= 0:
            start = max(0, idx - 120)
            return clean[start : start + max_chars].strip()
    return clean[:max_chars].strip()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_inline_xbrl_facts(html_text: str) -> List[InlineXbrlFact]:
    contexts = _parse_contexts(html_text)
    facts: List[InlineXbrlFact] = []
    pattern = re.compile(
        r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>",
        re.I | re.S,
    )
    for match in pattern.finditer(html_text):
        attrs = _parse_attrs(match.group(1))
        name = attrs.get("name")
        context_ref = attrs.get("contextRef")
        if not name or not context_ref:
            continue
        context = contexts.get(context_ref, {})
        facts.append(
            InlineXbrlFact(
                concept=_local_name(name),
                value=_parse_fact_value(match.group(2), attrs),
                year=_context_year(context),
                context_ref=context_ref,
                unit_ref=attrs.get("unitRef"),
                decimals=attrs.get("decimals"),
                scale=int(attrs.get("scale", "0") or 0),
                dimensions=context.get("dimensions", {}),
            )
        )
    return facts


def _build_concept_mapper_input(
    facts: List[InlineXbrlFact],
) -> Dict[str, Dict[int, float]]:
    xbrl_data: Dict[str, Dict[int, float]] = {}
    for fact in facts:
        if fact.value is None or fact.year is None:
            continue
        keys = []
        if not fact.dimensions:
            keys.append(fact.concept)
        keys.extend(_dimension_keys(fact))
        for key in keys:
            _set_if_unambiguous(xbrl_data, key, fact.year, fact.value)
    return xbrl_data


def _parse_contexts(html_text: str) -> Dict[str, Dict[str, Any]]:
    contexts: Dict[str, Dict[str, Any]] = {}
    pattern = re.compile(r"<xbrli:context\b([^>]*)>(.*?)</xbrli:context>", re.I | re.S)
    for match in pattern.finditer(html_text):
        attrs = _parse_attrs(match.group(1))
        context_id = attrs.get("id")
        if not context_id:
            continue
        block = match.group(2)
        dimensions = {
            _local_name(dimension): _local_name(member)
            for dimension, member in re.findall(
                r"<xbrldi:explicitMember\b[^>]*dimension=\"([^\"]+)\"[^>]*>(.*?)</xbrldi:explicitMember>",
                block,
                re.I | re.S,
            )
        }
        contexts[context_id] = {
            "instant": _first_tag_text(block, "xbrli:instant"),
            "end_date": _first_tag_text(block, "xbrli:endDate"),
            "dimensions": dimensions,
        }
    return contexts


def _parse_attrs(value: str) -> Dict[str, str]:
    return dict(re.findall(r"([A-Za-z_:][-A-Za-z0-9_:]*)=\"([^\"]*)\"", value))


def _first_tag_text(block: str, tag: str) -> Optional[str]:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.I | re.S)
    if not match:
        return None
    return html.unescape(match.group(1).strip())


def _context_year(context: Dict[str, Any]) -> Optional[int]:
    date = context.get("instant") or context.get("end_date")
    if not isinstance(date, str) or len(date) < 4:
        return None
    return int(date[:4])


def _parse_fact_value(inner_html: str, attrs: Dict[str, str]) -> Optional[float]:
    raw = re.sub(r"<[^>]+>", "", inner_html)
    text = html.unescape(raw).replace("\xa0", "").strip()
    if text in {"", "-", "—"}:
        return 0.0 if attrs.get("format", "").endswith("fixed-zero") else None
    negative = (text.startswith("(") and text.endswith(")")) or attrs.get("sign") == "-"
    normalized = text.strip("()").replace("$", "").replace(",", "").replace("%", "")
    try:
        value = float(normalized)
    except ValueError:
        return None
    value *= 10 ** int(attrs.get("scale", "0") or 0)
    return -value if negative else value


def _dimension_keys(fact: InlineXbrlFact) -> List[str]:
    keys = []
    for member in fact.dimensions.values():
        suffix = _member_suffix(member)
        if suffix:
            keys.append(f"{fact.concept}{suffix}")
    if len(fact.dimensions) > 1:
        suffix = "".join(_member_suffix(member) for member in fact.dimensions.values())
        if suffix:
            keys.append(f"{fact.concept}{suffix}")
    return keys


def _member_suffix(member: str) -> str:
    suffix = re.sub(r"Member$", "", _local_name(member))
    return re.sub(r"[^A-Za-z0-9]", "", suffix)


def _local_name(value: str) -> str:
    return html.unescape(value.strip()).split(":")[-1]


def _set_if_unambiguous(
    xbrl_data: Dict[str, Dict[int, float]],
    key: str,
    year: int,
    value: float,
) -> None:
    values = xbrl_data.setdefault(key, {})
    existing = values.get(year)
    if existing is None or abs(existing - value) <= 1e-9:
        values[year] = value
