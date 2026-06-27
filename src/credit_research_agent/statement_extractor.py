"""Financial statement table extraction from SEC 10-K HTML filings."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from credit_research_agent.sec_integration import FilingPackage


@dataclass
class StatementLineItem:
    """Normalized statement table row value for one fiscal year."""

    company: str
    ticker: str
    fiscal_year: int
    statement_type: str
    row_label: str
    normalized_label: str
    value: float | None
    unit: str
    period_end: str | None
    column_label: str
    xbrl_concept: str | None
    source_url: str
    accession_number: str
    confidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "ticker": self.ticker,
            "fiscal_year": self.fiscal_year,
            "statement_type": self.statement_type,
            "row_label": self.row_label,
            "normalized_label": self.normalized_label,
            "value": self.value,
            "unit": self.unit,
            "period_end": self.period_end,
            "column_label": self.column_label,
            "xbrl_concept": self.xbrl_concept,
            "source_url": self.source_url,
            "accession_number": self.accession_number,
            "confidence": self.confidence,
        }


def normalize_label(value: str) -> str:
    """Normalize a statement row label for deterministic matching."""
    text = html.unescape(value).replace("\xa0", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


class StatementTableExtractor:
    """Extract balance sheet, income statement, and cash flow rows from 10-K HTML."""

    def extract(self, filing: FilingPackage) -> List[StatementLineItem]:
        soup = BeautifulSoup(filing.html, "html.parser")
        items: List[StatementLineItem] = []
        for table in soup.find_all("table"):
            statement_type = self._classify_table(table)
            if statement_type is None:
                continue
            header_years = self._header_years(table)
            if not header_years:
                continue
            items.extend(self._extract_table_items(filing, table, statement_type, header_years))
        return items

    def _extract_table_items(
        self,
        filing: FilingPackage,
        table,
        statement_type: str,
        header_years: List[tuple[int, str]],
    ) -> List[StatementLineItem]:
        items: List[StatementLineItem] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            value_cells = [
                (idx, cell, self._cell_value(cell), self._cell_concept(cell))
                for idx, cell in enumerate(cells)
                if self._is_value_cell(cell)
            ]
            if not value_cells:
                continue

            first_value_idx = value_cells[0][0]
            label = self._row_label(cells[:first_value_idx])
            normalized = normalize_label(label)
            if not normalized or self._is_header_or_total_noise(normalized):
                continue

            year_count = min(len(header_years), len(value_cells))
            for offset in range(year_count):
                fiscal_year, column_label = header_years[offset]
                _idx, cell, value, concept = value_cells[offset]
                items.append(
                    StatementLineItem(
                        company=filing.company,
                        ticker=filing.ticker,
                        fiscal_year=fiscal_year,
                        statement_type=statement_type,
                        row_label=label,
                        normalized_label=normalized,
                        value=value,
                        unit="USD millions",
                        period_end=column_label,
                        column_label=column_label,
                        xbrl_concept=concept,
                        source_url=filing.primary_doc_url,
                        accession_number=filing.accession_number,
                        confidence="high" if concept else "medium",
                    )
                )
        return items

    @staticmethod
    def _classify_table(table) -> Optional[str]:
        text = normalize_label(table.get_text(" ", strip=True))
        if (
            (
                "cash flows from operating activities" in text
                or "operating activities" in text
            )
            and (
                "cash flows from investing activities" in text
                or "investing activities" in text
            )
            and (
                "cash flows from financing activities" in text
                or "financing activities" in text
            )
            and "net cash" in text
        ):
            return "cash_flow_statement"
        if (
            "current assets" in text
            and "current liabilities" in text
            and (
                "shareholders equity" in text
                or "shareowners equity" in text
                or "liabilities and equity" in text
            )
        ):
            return "balance_sheet"
        if (
            ("net income" in text or "net earnings" in text)
            and ("revenue" in text or "sales" in text)
            and "cash flows from operating activities" not in text
        ):
            return "income_statement"
        return None

    @staticmethod
    def _header_years(table) -> List[tuple[int, str]]:
        rows = table.find_all("tr")[:8]
        years: List[tuple[int, str]] = []
        seen = set()
        for row in rows:
            for cell in row.find_all(["td", "th"]):
                text = _clean_cell_text(cell)
                matches = re.findall(r"20\d{2}", text)
                if not matches:
                    continue
                year = int(matches[-1])
                if year not in seen:
                    years.append((year, text))
                    seen.add(year)
        return years

    @staticmethod
    def _cell_value(cell) -> float | None:
        concept = StatementTableExtractor._cell_concept(cell)
        ix = cell.find(lambda tag: tag.name and tag.name.lower().endswith("nonfraction"))
        if ix is not None:
            text = ix.get_text(" ", strip=True)
        else:
            text = _clean_cell_text(cell)
        return _parse_display_number(text, zero_for_dash=concept is not None)

    @staticmethod
    def _cell_concept(cell) -> str | None:
        ix = cell.find(lambda tag: tag.name and tag.name.lower().endswith("nonfraction"))
        if ix is None:
            return None
        name = ix.get("name")
        if not name:
            return None
        return name.split(":")[-1]

    @staticmethod
    def _is_value_cell(cell) -> bool:
        if cell.find(lambda tag: tag.name and tag.name.lower().endswith("nonfraction")):
            return True
        return _parse_display_number(_clean_cell_text(cell)) is not None

    @staticmethod
    def _row_label(cells) -> str:
        parts = []
        for cell in cells:
            text = _clean_cell_text(cell)
            if not text or text in {"$", "(", ")"}:
                continue
            parts.append(text)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    @staticmethod
    def _is_header_or_total_noise(normalized: str) -> bool:
        return normalized in {
            "year ended",
            "assets",
            "liabilities and shareholders equity",
            "current assets",
            "current liabilities",
            "cash flows from operating activities",
            "cash flows from investing activities",
            "cash flows from financing activities",
        }


def _clean_cell_text(cell) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True).replace("\xa0", " ")).strip()


def _parse_display_number(text: str, zero_for_dash: bool = False) -> float | None:
    value = html.unescape(text).replace("\xa0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    if value in {"", "$", "(", ")"}:
        return None
    if value in {"-", "—", "$ -", "$ —"}:
        return 0.0 if zero_for_dash else None
    if not re.search(r"\d", value):
        return None
    negative = "(" in value and ")" in value
    cleaned = value.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    cleaned = cleaned.replace("—", "0").replace("-", "-").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return -abs(number) if negative else number
