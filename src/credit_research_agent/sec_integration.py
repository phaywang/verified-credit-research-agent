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
import os
import re
import time
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


DEFAULT_SEC_USER_AGENT = (
    "VerifiedCreditResearchAgent/0.1 contact@example.com "
    "(educational portfolio project; set SEC_USER_AGENT for maintainer contact)"
)
SEC_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

def _sec_headers() -> Dict[str, str]:
    """Return SEC-compliant headers for EDGAR requests."""

    return {
        "User-Agent": os.getenv("SEC_USER_AGENT", DEFAULT_SEC_USER_AGENT),
        "Accept-Encoding": "gzip, deflate",
    }


def _sec_get(
    url: str,
    timeout: int = 10,
    max_attempts: int = 3,
    backoff_seconds: float = 0.5,
):
    """GET helper that attaches SEC-friendly headers and retries transient failures."""

    if requests is None:
        raise ImportError("requests library required for SEC API calls")

    last_error = None
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=_sec_headers())
            status_code = getattr(response, "status_code", None)
            if (
                isinstance(status_code, int)
                and status_code in SEC_RETRYABLE_STATUS_CODES
                and attempt < attempts
            ):
                logger.warning(
                    "Retrying SEC request after HTTP %s for %s (attempt %s/%s)",
                    status_code,
                    url,
                    attempt,
                    attempts,
                )
                time.sleep(backoff_seconds * attempt)
                continue
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            logger.warning(
                "Retrying SEC request after transient error for %s (attempt %s/%s): %s",
                url,
                attempt,
                attempts,
                exc,
            )
            time.sleep(backoff_seconds * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"SEC request failed without response: {url}")


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


_COMPANY_ALIASES = {
    "google": "alphabet",
    "google llc": "alphabet",
    "jp morgan": "jpmorgan chase",
    "j p morgan": "jpmorgan chase",
    "jpmorgan": "jpmorgan chase",
    "facebook": "meta platforms",
    "meta": "meta platforms",
}


def _normalize_company_query(value: str) -> str:
    """Normalize user company input and SEC legal titles for matching."""
    text = value.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [
        token for token in text.split()
        if token not in {
            "inc",
            "incorporated",
            "corp",
            "corporation",
            "co",
            "company",
            "ltd",
            "plc",
            "class",
            "common",
            "stock",
            "the",
        }
    ]
    return " ".join(tokens).strip()


def _ambiguous_company_message(query: str, matches: List[Dict]) -> str:
    examples = ", ".join(
        f"{entry.get('ticker')} ({entry.get('title')})"
        for entry in matches[:5]
    )
    return (
        f"Ambiguous company query '{query}'. Matching SEC issuers include: "
        f"{examples}. Try a ticker or more complete legal name."
    )


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
            CIK as zero-padded string (e.g., "0000789019" for MSFT)

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

    def resolve_company_query(self, query: str) -> CompanyInfo:
        """Resolve a ticker, company name, or alias to SEC company metadata."""
        normalized_query = _normalize_company_query(query)
        if not normalized_query:
            raise CompanyNotFoundError("Company or ticker input is required.")

        tickers = self._load_tickers_json()

        # Exact ticker match wins over company-name matching.
        query_upper = query.strip().upper()
        for entry in tickers.values():
            if entry.get("ticker", "").upper() == query_upper:
                return self.get_company_info(str(entry.get("cik_str")).zfill(10))

        alias_query = _COMPANY_ALIASES.get(normalized_query, normalized_query)

        exact_matches = [
            entry for entry in tickers.values()
            if _normalize_company_query(entry.get("title", "")) == alias_query
        ]
        if len(exact_matches) == 1:
            return self.get_company_info(str(exact_matches[0].get("cik_str")).zfill(10))

        prefix_matches = [
            entry for entry in tickers.values()
            if _normalize_company_query(entry.get("title", "")).startswith(alias_query)
        ]
        if len(prefix_matches) == 1:
            return self.get_company_info(str(prefix_matches[0].get("cik_str")).zfill(10))
        if len(prefix_matches) > 1:
            raise CompanyNotFoundError(_ambiguous_company_message(query, prefix_matches))

        contains_matches = [
            entry for entry in tickers.values()
            if alias_query in _normalize_company_query(entry.get("title", ""))
        ]
        if len(contains_matches) == 1:
            return self.get_company_info(str(contains_matches[0].get("cik_str")).zfill(10))
        if len(contains_matches) > 1:
            raise CompanyNotFoundError(_ambiguous_company_message(query, contains_matches))

        raise CompanyNotFoundError(
            f"Company query '{query}' was not found in SEC EDGAR ticker metadata. "
            "Try a ticker or a more complete legal company name."
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
            response = _sec_get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            cik_info = data.get("cik") or data.get("cik_str")
            if not cik_info:
                raise CompanyNotFoundError(f"CIK {cik} not found in SEC EDGAR")

            # Extract company name
            name = data.get("name") or data.get("entityName", "Unknown Company")
            tickers = data.get("tickers", [])
            exchanges = data.get("exchanges", [])

            # Find available annual filing years from submissions metadata.
            fiscal_years: set[int] = set()
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            report_dates = filings.get("reportDate", [])
            filing_dates = filings.get("filingDate", [])
            for i, form_type in enumerate(forms):
                if form_type not in {"10-K", "10-K/A"}:
                    continue
                date = ""
                if i < len(report_dates):
                    date = report_dates[i]
                if not date and i < len(filing_dates):
                    date = filing_dates[i]
                if date:
                    try:
                        fiscal_years.add(int(date[:4]))
                    except ValueError:
                        pass

            sorted_years = sorted(fiscal_years, reverse=True)

            return CompanyInfo(
                name=name,
                cik=cik_padded,
                ticker=tickers[0] if tickers else "",
                sic=str(data.get("sic", "")),
                sector=exchanges[0] if exchanges else "",
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
            response = _sec_get(self.SEC_TICKERS_URL, timeout=10)
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
    SEC_COMPANYFACTS_API = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
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
            response = _sec_get(url, timeout=10)
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
                                cik_no_leading_zeroes = str(int(cik_padded))
                                xbrl_url = (
                                    f"{self.SEC_ARCHIVES}/edgar/data/"
                                    f"{cik_no_leading_zeroes}/{acc}/{primary}"
                                )
                                logger.info(f"Fetching XBRL from {xbrl_url}")
                                xbrl_response = _sec_get(xbrl_url, timeout=30)
                                xbrl_response.raise_for_status()
                                return xbrl_response.text

            raise FilingNotFoundError(
                f"No 10-K filing found for CIK {cik} in fiscal year {fiscal_year}"
            )

        except requests.RequestException as e:
            raise FilingNotFoundError(
                f"Failed to fetch 10-K for CIK {cik}, year {fiscal_year}: {e}"
            )

    def fetch_companyfacts(self, cik: str) -> Dict:
        """Fetch SEC companyfacts JSON for structured XBRL facts.

        This endpoint is preferred for deterministic GAAP metric extraction. The
        10-K primary document is often inline XBRL HTML, while companyfacts is
        already normalized as SEC JSON.
        """
        if requests is None:
            raise ImportError("requests library required for SEC API calls")

        cik_padded = str(cik).zfill(10)
        try:
            url = self.SEC_COMPANYFACTS_API.format(cik=cik_padded)
            response = _sec_get(url, timeout=20)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            raise FilingNotFoundError(
                f"Failed to fetch companyfacts for CIK {cik}: {e}"
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
            response = _sec_get(url, timeout=10)
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

    def extract_metrics_from_companyfacts(
        self,
        companyfacts: Dict,
        metric_selectors: Dict[str, List[str]],
        fiscal_year: int,
    ) -> Dict[str, MetricValue]:
        """Extract annual metrics from SEC companyfacts JSON.

        Args:
            companyfacts: Raw JSON from SEC companyfacts endpoint.
            metric_selectors: Mapping of metric name to candidate concept names.
            fiscal_year: Fiscal year to extract.
        """
        results: Dict[str, MetricValue] = {}
        facts = companyfacts.get("facts", {})

        for metric_name, concepts in metric_selectors.items():
            for concept in concepts:
                fact = self._extract_companyfact(facts, concept, fiscal_year)
                if fact is None:
                    continue

                value = fact.get("val")
                if value is None:
                    continue

                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue

                if abs(numeric_value) > 1_000_000:
                    numeric_value = numeric_value / 1_000_000

                results[metric_name] = MetricValue(
                    metric_name=metric_name,
                    value=numeric_value,
                    unit=fact.get("unit", "USD"),
                    fiscal_year=fiscal_year,
                    xbrl_concept=concept,
                    source="SEC companyfacts",
                )
                break

        logger.info(
            "Extracted %s metrics from SEC companyfacts for fiscal year %s",
            len(results),
            fiscal_year,
        )
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

    def _extract_companyfact(
        self,
        facts: Dict,
        concept: str,
        fiscal_year: int,
    ) -> Optional[Dict]:
        """Pick the best matching annual companyfact for a concept."""

        concept_name = concept.split(":")[-1]
        concept_data = None
        for namespace_facts in facts.values():
            if concept_name in namespace_facts:
                concept_data = namespace_facts[concept_name]
                break

        if not concept_data:
            return None

        candidates = []
        for unit, entries in concept_data.get("units", {}).items():
            for entry in entries:
                if entry.get("fy") != fiscal_year:
                    continue
                if entry.get("form") not in {"10-K", "10-K/A"}:
                    continue
                enriched = dict(entry)
                enriched["unit"] = unit
                candidates.append(enriched)

        if not candidates:
            return None

        def sort_key(entry: Dict):
            fp_rank = 1 if entry.get("fp") == "FY" else 0
            filed = entry.get("filed", "")
            end = entry.get("end", "")
            return (fp_rank, filed, end)

        return sorted(candidates, key=sort_key, reverse=True)[0]
