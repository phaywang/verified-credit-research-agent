"""SEC EDGAR integration for universal company support.

Provides access to SEC's public company data:
- Ticker → CIK lookup
- Company metadata
- 10-K XBRL filing downloads
- XBRL parsing and metric extraction
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from urllib.error import URLError

try:
    import requests
except ImportError:
    requests = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class CompanyInfo:
    """Company metadata from SEC EDGAR"""
    name: str
    cik: str
    ticker: str
    sic: str  # Standard Industrial Classification code
    sector: str
    fiscal_years_available: List[int]


@dataclass
class MetricValue:
    """Extracted metric value from XBRL"""
    metric_name: str
    value: float | None
    unit: str
    fiscal_year: int
    xbrl_concept: str
    source: str  # "XBRL" or "text_extraction"


class CompanyNotFoundError(Exception):
    """Raised when company/ticker is not found in SEC EDGAR"""
    pass


class FilingNotFoundError(Exception):
    """Raised when 10-K filing not found for company/year"""
    pass


class SECCompanyLookup:
    """Query SEC EDGAR for company information."""

    # SEC public API endpoints
    SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SEC_EDGAR_API = "https://data.sec.gov/submissions/CIK{cik}.json"
    SEC_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar"

    def __init__(self, cache_dir: Path | None = None):
        """Initialize SEC company lookup.

        Args:
            cache_dir: Directory to cache SEC tickers JSON (default: ~/.sec_cache)
        """
        self.cache_dir = cache_dir or Path.home() / ".sec_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._tickers_cache: Optional[Dict] = None

    def get_cik_by_ticker(self, ticker: str) -> str:
        """Lookup CIK (Central Index Key) by stock ticker.

        Args:
            ticker: Stock ticker (e.g., "AAPL", "TSLA", "GOOGL")

        Returns:
            CIK as zero-padded string (e.g., "0000000789019" for MSFT)

        Raises:
            CompanyNotFoundError: If ticker not found in SEC database
        """
        tickers = self._load_tickers_json()

        ticker_upper = ticker.upper()
        for entry in tickers.values():
            if entry.get("ticker") == ticker_upper:
                cik = entry.get("cik_str")
                if cik is not None:
                    return str(cik).zfill(10)

        raise CompanyNotFoundError(
            f"Ticker '{ticker}' not found in SEC EDGAR. "
            f"Check that it's a valid US stock ticker."
        )

    def get_company_info(self, cik: str) -> CompanyInfo:
        """Fetch company metadata from SEC EDGAR.

        Args:
            cik: CIK number (with or without zero-padding)

        Returns:
            CompanyInfo with name, sector, available fiscal years

        Raises:
            CompanyNotFoundError: If CIK not found or API error
        """
        cik_padded = str(cik).zfill(10)

        try:
            if requests is None:
                raise ImportError("requests library required for SEC API calls")

            # Fetch company data
            url = self.SEC_EDGAR_API.format(cik=cik_padded)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            company_facts = data.get("facts", {}).get("us-gaap", {})
            cik_info = data.get("cik_str")
            if not cik_info:
                raise CompanyNotFoundError(f"CIK {cik} not found in SEC EDGAR")

            # Extract company name
            name = data.get("entityName", "Unknown Company")

            # Find available fiscal years from XBRL data
            fiscal_years: set[int] = set()
            for concept_data in company_facts.values():
                for unit_data in concept_data.get("units", {}).values():
                    for entry in unit_data:
                        if "end" in entry:
                            year_str = entry["end"][:4]
                            try:
                                fiscal_years.add(int(year_str))
                            except ValueError:
                                pass

            sorted_years = sorted(fiscal_years, reverse=True)

            return CompanyInfo(
                name=name,
                cik=cik_padded,
                ticker="",  # Would need reverse lookup
                sic="",  # Not reliably available in this API
                sector="",  # Would require additional lookup
                fiscal_years_available=sorted_years,
            )

        except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
            raise CompanyNotFoundError(
                f"Failed to fetch company info for CIK {cik}: {e}"
            )

    def _load_tickers_json(self) -> Dict:
        """Load SEC company tickers JSON (cached locally).

        Returns:
            Dict mapping numeric index to ticker info {index: {ticker, cik_str}}
        """
        if self._tickers_cache is not None:
            return self._tickers_cache

        cache_path = self.cache_dir / "company_tickers.json"

        # Try to load from cache first
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    self._tickers_cache = json.load(f)
                logger.info(f"Loaded cached tickers from {cache_path}")
                return self._tickers_cache
            except (json.JSONDecodeError, IOError):
                logger.warning(f"Failed to load cached tickers, will fetch fresh")

        # Fetch from SEC website
        try:
            if requests is None:
                raise ImportError("requests library required for SEC API calls")

            logger.info(f"Fetching SEC tickers from {self.SEC_TICKERS_URL}")
            response = requests.get(self.SEC_TICKERS_URL, timeout=10)
            response.raise_for_status()
            tickers = response.json()

            # Save to cache
            with open(cache_path, "w") as f:
                json.dump(tickers, f, indent=2)
            logger.info(f"Cached {len(tickers)} tickers to {cache_path}")

            self._tickers_cache = tickers
            return tickers

        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Failed to fetch SEC tickers: {e}")
            raise CompanyNotFoundError(
                f"Could not fetch SEC company tickers: {e}"
            )


class SEC10KFetcher:
    """Download 10-K XBRL filings from SEC EDGAR."""

    SEC_DATA_API = "https://data.sec.gov/submissions/CIK{cik}.json"
    SEC_ARCHIVES = "https://www.sec.gov/Archives"

    def __init__(self):
        """Initialize 10-K fetcher."""
        pass

    def fetch_10k_xbrl(self, cik: str, fiscal_year: int) -> str:
        """Download 10-K XBRL instance document.

        Args:
            cik: CIK number (zero-padded)
            fiscal_year: Fiscal year (e.g., 2023)

        Returns:
            Raw XBRL XML content

        Raises:
            FilingNotFoundError: If 10-K not found for this year
        """
        if requests is None:
            raise ImportError("requests library required for SEC API calls")

        cik_padded = str(cik).zfill(10)

        try:
            # Fetch filing index
            url = self.SEC_DATA_API.format(cik=cik_padded)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Find 10-K filing for this fiscal year
            filings = data.get("filings", {}).get("recent", {})
            form = filings.get("form", [])
            accession = filings.get("accessionNumber", [])
            filing_date = filings.get("filingDate", [])
            primary_doc = filings.get("primaryDocument", [])

            # Look for 10-K form in this year
            for i, form_type in enumerate(form):
                if form_type == "10-K":
                    # Check if filing date is in fiscal_year
                    if i < len(filing_date):
                        file_year = int(filing_date[i][:4])
                        if file_year == fiscal_year or file_year == fiscal_year + 1:
                            # Found matching 10-K
                            acc = accession[i].replace("-", "")
                            primary = primary_doc[i] if i < len(primary_doc) else None

                            if primary:
                                xbrl_url = (
                                    f"{self.SEC_ARCHIVES}/{acc.replace('-', '')}/{primary}"
                                )
                                logger.info(f"Fetching XBRL from {xbrl_url}")
                                xbrl_response = requests.get(xbrl_url, timeout=30)
                                xbrl_response.raise_for_status()
                                return xbrl_response.text

            raise FilingNotFoundError(
                f"No 10-K filing found for CIK {cik} in fiscal year {fiscal_year}"
            )

        except requests.RequestException as e:
            raise FilingNotFoundError(
                f"Failed to fetch 10-K for CIK {cik}, year {fiscal_year}: {e}"
            )

    def fetch_10k_narrative(self, cik: str, fiscal_year: int) -> str:
        """Fetch narrative 10-K text (fallback for metric extraction).

        Args:
            cik: CIK number
            fiscal_year: Fiscal year

        Returns:
            Full 10-K text
        """
        # Placeholder: would implement HTML scraping of 10-K document
        raise NotImplementedError("Narrative 10-K fetching not yet implemented")

    def get_available_years(self, cik: str) -> List[int]:
        """List fiscal years with 10-K filings available.

        Args:
            cik: CIK number

        Returns:
            Sorted list of available fiscal years
        """
        if requests is None:
            raise ImportError("requests library required for SEC API calls")

        cik_padded = str(cik).zfill(10)

        try:
            url = self.SEC_DATA_API.format(cik=cik_padded)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            filings = data.get("filings", {}).get("recent", {})
            form = filings.get("form", [])
            filing_date = filings.get("filingDate", [])

            years: set[int] = set()
            for i, form_type in enumerate(form):
                if form_type == "10-K" and i < len(filing_date):
                    year = int(filing_date[i][:4])
                    years.add(year)

            return sorted(years, reverse=True)

        except requests.RequestException as e:
            logger.error(f"Failed to fetch available years for CIK {cik}: {e}")
            return []


class XBRLParser:
    """Parse XBRL 10-K files and extract financial metrics."""

    def __init__(self):
        """Initialize XBRL parser."""
        try:
            import xml.etree.ElementTree as ET
            self.ET = ET
        except ImportError:
            self.ET = None

    def extract_metrics(
        self,
        xbrl_content: str,
        metric_names: List[str],
        fiscal_year: int,
    ) -> Dict[str, MetricValue]:
        """Extract metrics from XBRL content.

        Args:
            xbrl_content: Raw XBRL XML
            metric_names: List of metric names to extract
            fiscal_year: Fiscal year (for matching contexts)

        Returns:
            Dict mapping metric_name → MetricValue
        """
        if self.ET is None:
            raise ImportError("xml.etree.ElementTree required for XBRL parsing")

        results: Dict[str, MetricValue] = {}

        try:
            root = self.ET.fromstring(xbrl_content)

            # Build context lookup: context_id → end_date
            contexts = self._extract_contexts(root)

            # Find contexts matching the fiscal year
            matching_contexts = [
                (ctx_id, date) for ctx_id, date in contexts.items()
                if date and date[:4] == str(fiscal_year)
            ]

            if not matching_contexts:
                logger.warning(f"No contexts found for fiscal year {fiscal_year}")
                return results

            # XBRL concept mapping (simplified)
            concept_map = {
                "total_debt": ["us-gaap:Debt", "us-gaap:ShortTermBorrowings", "us-gaap:LongTermDebt"],
                "shareholders_equity": ["us-gaap:StockholdersEquity", "us-gaap:ShareholdersEquity"],
                "total_assets": ["us-gaap:Assets"],
                "total_liabilities": ["us-gaap:Liabilities"],
                "interest_expense": ["us-gaap:InterestExpense"],
                "operating_cash_flow": ["us-gaap:OperatingActivitiesCashFlow"],
                "current_assets": ["us-gaap:AssetsCurrent"],
                "current_liabilities": ["us-gaap:LiabilitiesCurrent"],
            }

            # Extract each requested metric
            for metric_name in metric_names:
                xbrl_concepts = concept_map.get(metric_name, [])
                if not xbrl_concepts:
                    logger.warning(f"No XBRL concept mapping for {metric_name}")
                    continue

                # Try each concept (fallback priority)
                for concept in xbrl_concepts:
                    value = self._extract_concept_value(root, concept, matching_contexts)

                    if value is not None:
                        results[metric_name] = MetricValue(
                            metric_name=metric_name,
                            value=value,
                            unit="USD",
                            fiscal_year=fiscal_year,
                            xbrl_concept=concept,
                            source="XBRL"
                        )
                        break

            logger.info(f"Extracted {len(results)} metrics from XBRL")

        except self.ET.ParseError as e:
            logger.error(f"Failed to parse XBRL: {e}")

        return results

    def extract_fiscal_year(self, xbrl_content: str) -> int:
        """Extract fiscal year from XBRL."""
        if self.ET is None:
            raise ImportError("xml.etree.ElementTree required for XBRL parsing")

        try:
            root = self.ET.fromstring(xbrl_content)
            contexts = self._extract_contexts(root)

            # Return the most recent fiscal year found
            years = set()
            for date in contexts.values():
                if date:
                    try:
                        year = int(date[:4])
                        years.add(year)
                    except (ValueError, IndexError):
                        pass

            return max(years) if years else 0

        except self.ET.ParseError:
            return 0

    def get_available_metrics(self, xbrl_content: str) -> List[str]:
        """List all metrics available in XBRL file."""
        if self.ET is None:
            return []

        try:
            root = self.ET.fromstring(xbrl_content)
            metrics = set()

            # Find all elements with us-gaap namespace (typically financial concepts)
            for elem in root.iter():
                tag = elem.tag
                # Check if it's a namespaced element
                if "}" in tag:
                    namespace, local_name = tag.split("}", 1)
                    # Capture us-gaap or other XBRL financial namespaces
                    if "xbrl.us" in namespace or "xbrl.ifrg" in namespace:
                        metrics.add(local_name)
                elif not tag.endswith("context"):  # Skip structural elements
                    metrics.add(tag)

            return sorted(list(metrics))

        except self.ET.ParseError:
            return []

    def _extract_contexts(self, root) -> Dict[str, str]:
        """Extract context mappings: context_id → end_date.

        Returns: {context_id: "YYYY-MM-DD"}
        """
        contexts: Dict[str, str] = {}

        # Handle different namespace styles
        # Try direct children first, then search recursively
        for context in root:
            if context.tag.endswith("context"):
                context_id = context.get("id", "")

                # Find period element or instant
                for child in context:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if tag in ("instant", "endDate"):
                        contexts[context_id] = (child.text or "").strip()
                        break

        return contexts

    def _extract_concept_value(
        self, root, concept: str, matching_contexts: List[tuple]
    ) -> Optional[float]:
        """Extract numeric value for a concept from matching contexts.

        Args:
            concept: XBRL concept like "us-gaap:Debt" or just "Debt"
        """

        matching_ctx_ids = set(ctx_id for ctx_id, _ in matching_contexts)

        # Extract the local concept name (part after :)
        local_concept = concept.split(":")[-1] if ":" in concept else concept

        for elem in root.iter():
            # Extract the local name from the full tag (with or without namespace)
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            context_ref = elem.get("contextRef", "").strip()
            text_value = (elem.text or "").strip()

            if tag == local_concept and context_ref in matching_ctx_ids and text_value:
                try:
                    value = float(text_value)
                    # Normalize to millions if needed
                    if value > 1000000:
                        value = value / 1000000
                    return value
                except ValueError:
                    continue

        return None
