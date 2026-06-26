"""SEC filing fetcher for the Ford Milestone 1 demo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests

from credit_research_agent.config import DATA_DIR, SEC_USER_AGENT
from credit_research_agent.schemas import FilingDocument, write_json


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash}/{primary_doc}"


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def _archive_headers() -> Dict[str, str]:
    headers = _headers()
    headers["Host"] = "www.sec.gov"
    return headers


def accession_without_dashes(accession_number: str) -> str:
    return accession_number.replace("-", "")


def build_archive_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_int = str(int(cik))
    return SEC_ARCHIVES_URL.format(
        cik_int=cik_int,
        accession_no_dash=accession_without_dashes(accession_number),
        primary_doc=primary_document,
    )


def _iter_recent_filings(submissions: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for idx, form in enumerate(forms):
        yield {
            "form": form,
            "filing_date": recent.get("filingDate", [None])[idx],
            "report_date": recent.get("reportDate", [None])[idx],
            "accession_number": recent.get("accessionNumber", [None])[idx],
            "primary_document": recent.get("primaryDocument", [None])[idx],
        }


def _fiscal_year_from_report_date(report_date: Optional[str]) -> Optional[int]:
    if not report_date or len(report_date) < 4:
        return None
    try:
        return int(report_date[:4])
    except ValueError:
        return None


def _select_filing(
    filings: list[Dict[str, Any]],
    fiscal_year: int,
    filing_type: str,
) -> tuple[Dict[str, Any], bool, Optional[str]]:
    exact = [
        filing
        for filing in filings
        if filing.get("form") == filing_type
        and _fiscal_year_from_report_date(filing.get("report_date")) == fiscal_year
    ]
    if exact:
        return exact[0], False, None

    substitutes = [
        filing
        for filing in filings
        if filing.get("form") in {"10-K", "10-Q"}
        and filing.get("accession_number")
        and filing.get("primary_document")
    ]
    if not substitutes:
        raise LookupError(
            f"No usable {filing_type}, 10-K, or 10-Q filings found for substitution."
        )

    selected = substitutes[0]
    note = (
        f"Requested fiscal {fiscal_year} {filing_type} was unavailable in SEC "
        f"recent filings. Used {selected.get('form')} filed on "
        f"{selected.get('filing_date')} with report date {selected.get('report_date')}."
    )
    return selected, True, note


def fetch_company_filing(
    company: str,
    ticker: str,
    cik: str,
    fiscal_year: int,
    filing_type: str,
    output_root: Path = DATA_DIR / "raw" / "sec" / "ford",
) -> FilingDocument:
    """Fetch and persist one Ford filing from SEC submissions metadata."""

    submissions_url = SEC_SUBMISSIONS_URL.format(cik=cik)
    response = requests.get(submissions_url, headers=_headers(), timeout=30)
    response.raise_for_status()
    filings = list(_iter_recent_filings(response.json()))

    selected, is_substitution, substitution_note = _select_filing(
        filings, fiscal_year, filing_type
    )
    accession_number = selected["accession_number"]
    primary_document = selected["primary_document"]
    source_url = build_archive_url(cik, accession_number, primary_document)

    filing_response = requests.get(source_url, headers=_archive_headers(), timeout=60)
    filing_response.raise_for_status()

    actual_fiscal_year = (
        _fiscal_year_from_report_date(selected.get("report_date")) or fiscal_year
    )
    year_dir = output_root / str(fiscal_year)
    year_dir.mkdir(parents=True, exist_ok=True)
    filing_path = year_dir / "filing.html"
    metadata_path = year_dir / "filing_metadata.json"
    filing_path.write_text(filing_response.text, encoding="utf-8", errors="ignore")

    document = FilingDocument(
        company=company,
        ticker=ticker,
        cik=cik,
        fiscal_year=actual_fiscal_year,
        filing_type=selected["form"],
        filing_date=selected["filing_date"],
        accession_number=accession_number,
        source_url=source_url,
        local_path=str(filing_path),
        is_substitution=is_substitution,
        requested_fiscal_year=fiscal_year,
        requested_filing_type=filing_type,
        substitution_note=substitution_note,
    )
    write_json(metadata_path, document)
    return document


def load_filing_document(metadata_path: Path) -> FilingDocument:
    return FilingDocument.model_validate_json(metadata_path.read_text(encoding="utf-8"))

