# Verified Credit Research Agent - Milestone 5
## Universal SEC Integration + Multi-Company Analysis

**Status**: Design phase (ready for implementation)  
**Objective**: Transform from configuration-driven framework into universal product. Accept any stock ticker, automatically fetch real SEC data, generate verified briefs for any company.

**Key Innovation**: SEC EDGAR integration eliminates manual data configuration. System becomes truly generalizable: zero human data entry needed.

---

## Executive Summary

M5 builds on M1-M4 foundation to create a **universal credit research product**:

### M1-M4 Achievement
```
Fixed harness: Ford only (hardcoded)
    ↓ (Expansion Phase 1)
Flexible framework: Any configured company (config files)
    ↓ (M5)
Universal product: Any SEC company (automated data fetch)
```

### M5 Vision
```
User Input:
  ticker="TSLA"
  risk_theme="leverage_analysis"
  years=[2023, 2024]

System (fully automated):
  1. Lookup: TSLA → CIK 1318605
  2. Fetch: SEC EDGAR → 10-K XBRL for 2023, 2024
  3. Parse: XBRL → Extract debt, equity, interest metrics
  4. Analyze: Metrics → Generate verified brief
  5. Output: Markdown brief with verified numbers + trace

No manual config. No hardcoding. Just SEC EDGAR API.
```

---

## Architecture: M5 Adds SEC Integration Layer

```
Previous (M1-M4):
  User Question
    ↓
  TaskSpec Parser (hardcoded or config)
    ↓
  M3 ReAct Agent
    ↓
  Brief Generator (uses pre-configured metrics)
    ↓
  Final Brief

M5 (New Flow):
  Ticker Input ("TSLA")
    ↓
  SEC Company Lookup [NEW]
    ↓ (CIK, company name, sector)
  SEC 10-K Fetcher [NEW]
    ↓ (Download XBRL for each year)
  XBRL Parser [NEW]
    ↓ (Extract metrics from XBRL)
  TaskSpec Generator (existing, enhanced)
    ↓
  M3 ReAct Agent (unchanged)
    ↓
  Brief Generator (unchanged)
    ↓
  Final Brief (real data, not mock)
```

---

## Phase 2: SEC Automation (M5 Core)

### 2.1 SEC Company Lookup

**File**: `src/credit_research_agent/sec_integration.py`

**Component: `SECCompanyLookup`**

```python
class SECCompanyLookup:
    """Query SEC EDGAR for company metadata"""
    
    def get_cik_by_ticker(ticker: str) -> str:
        """
        Lookup CIK (Central Index Key) for a stock ticker.
        
        Uses SEC's public company tickers JSON:
        https://www.sec.gov/files/company_tickers.json
        
        Returns: CIK as string (e.g., "0001318605" for Tesla)
        """
    
    def get_company_info(cik: str) -> CompanyInfo:
        """
        Fetch company metadata from SEC EDGAR.
        
        Uses EDGAR API: /cgi-bin/browse-edgar
        
        Returns CompanyInfo:
          - name: "Tesla Inc."
          - sector: "Manufacturing"
          - sic: "3711" (motor vehicles)
          - latest_10k_accession: "0001193125-24-..."
          - fiscal_years_available: [2022, 2023, 2024]
        """
```

**Key Data Sources**:
- `/company_tickers.json` — Public ticker → CIK mapping (cached locally)
- `/cgi-bin/browse-edgar?action=getcompany&CIK=...` — Company details
- EDGAR submission feeds — Latest 10-K filings

---

### 2.2 SEC 10-K Fetcher

**Component: `SEC10KFetcher`**

```python
class SEC10KFetcher:
    """Download 10-K XBRL filings from SEC EDGAR"""
    
    def fetch_10k_xbrl(cik: str, fiscal_year: int) -> str:
        """
        Download 10-K XBRL instance document.
        
        Flow:
        1. Query EDGAR index for 10-K submissions in fiscal_year
        2. Find submission with form type "10-K"
        3. Locate XBRL instance file (usually 'XXX_*.xml')
        4. Download from https://www.sec.gov/Archives/...
        5. Return raw XBRL content
        
        Args:
          cik: "0001318605" (Tesla)
          fiscal_year: 2023
        
        Returns: Raw XBRL XML (≈5-50 MB)
        
        Raises:
          CompanyNotFoundError: CIK doesn't exist
          FilingNotFoundError: No 10-K for this year
          DownloadError: Network/access error
        """
    
    def fetch_10k_narrative(cik: str, fiscal_year: int) -> str:
        """
        Fetch narrative 10-K (full text).
        
        Used as fallback for metrics not in XBRL.
        Returns: Full 10-K text (~200-500 pages)
        """
    
    def get_available_years(cik: str) -> List[int]:
        """
        List fiscal years with 10-K filings available.
        Returns: [2022, 2023, 2024]
        """
```

**XBRL Structure** (what we're downloading):
```xml
<xbrl>
  <context id="Current_2024">
    <period>
      <instant>2024-12-31</instant>
    </period>
    <entity>
      <identifier scheme="CIK">0001318605</identifier>
    </entity>
  </context>
  
  <us-gaap:Assets contextRef="Current_2024" unitRef="USD">
    12345000000  <!-- Assets in dollars -->
  </us-gaap:Assets>
  
  <us-gaap:Liabilities contextRef="Current_2024" unitRef="USD">
    5678000000   <!-- Liabilities in dollars -->
  </us-gaap:Liabilities>
  
  <!-- ... hundreds of financial metrics ... -->
</xbrl>
```

---

### 2.3 XBRL Parser

**Component: `XBRLParser`**

```python
class XBRLParser:
    """Parse XBRL 10-K files and extract financial metrics"""
    
    def extract_metrics(
        self,
        xbrl_content: str,
        metric_names: List[str],
        fiscal_year: int
    ) -> Dict[str, MetricValue]:
        """
        Extract specific metrics from XBRL.
        
        Args:
          xbrl_content: Raw XBRL XML
          metric_names: ["total_debt", "shareholders_equity", "interest_expense"]
          fiscal_year: 2024
        
        Process:
        1. Parse XML
        2. For each metric_name:
           a. Lookup XBRL concept (e.g., "us-gaap:Debt" for total_debt)
           b. Find context matching fiscal_year
           c. Extract value from instant/duration
           d. Apply unit conversion (millions → standard unit)
           e. Store with metadata (concept, unit, context)
        3. Return {metric_name: MetricValue}
        
        Returns:
          {
            "total_debt": MetricValue(
              value=110.5,
              unit="USD billions",
              xbrl_concept="us-gaap:Debt",
              fiscal_year=2024,
              context="Current_2024"
            ),
            ...
          }
        """
    
    def extract_fiscal_year(self, xbrl_content: str) -> int:
        """Extract fiscal year-end date from XBRL"""
    
    def get_available_metrics(self, xbrl_content: str) -> List[str]:
        """List all metrics present in this XBRL file"""
```

**XBRL Concept Mapping** (maintained in config):

```yaml
xbrl_concepts:
  total_debt:
    - us-gaap:Debt
    - us-gaap:DebtAndEquitySourceOfCreditLine
  shareholders_equity:
    - us-gaap:StockholdersEquity
    - us-gaap:ShareholdersEquity
  interest_expense:
    - us-gaap:InterestExpense
    - us-gaap:InterestAndDebtExpense
```

**Key Challenge**: Different companies use different XBRL concepts
- Solution: Concept mapping + fallback hierarchy
- Example: Try "us-gaap:Debt", if not found try alternative concepts

---

### 2.4 Universal Analyzer

**Component: `UniversalCreditAnalyzer`**

```python
class UniversalCreditAnalyzer:
    """End-to-end analysis for any SEC company"""
    
    def analyze(
        self,
        ticker: str,
        risk_theme: str,
        years: List[int]
    ) -> AnalysisResult:
        """
        Complete analysis: ticker → verified brief
        
        Flow:
        1. lookup_company(ticker)
           → CIK, name, sector
        
        2. fetch_10k_data(cik, years)
           → XBRL content for each year
        
        3. parse_xbrl(xbrl_content)
           → Extracted metrics for each year
        
        4. create_verified_metrics(
             company_name, theme, metrics
           )
           → VerifiedMetricsSet (M4 compatible)
        
        5. generate_brief(company, theme, metrics)
           → Markdown brief with verified numbers
        
        6. return AnalysisResult
           → Brief + metrics + trace
        
        Returns:
          AnalysisResult(
            company="Tesla Inc.",
            ticker="TSLA",
            theme="leverage_analysis",
            years=[2023, 2024],
            brief="# Tesla Inc. — ...",
            metrics={
              2023: [MetricResult(...), ...],
              2024: [MetricResult(...), ...]
            },
            trace=[
              {"step": "lookup_company", "status": "success"},
              {"step": "fetch_10k_data", "status": "success"},
              ...
            ],
            status="verified"
          )
        """
```

**Error Handling**:
```python
# Graceful degradation
if xbrl_metric_not_found:
    fallback_to_narrative_extraction()

if_no_historical_data:
    return current_year_only_analysis()

if_company_not_found:
    raise CompanyNotFoundError(
        f"Ticker {ticker} not found in SEC EDGAR"
    )
```

---

### 2.5 Enhanced Task Generator

**Modification**: `src/credit_research_agent/task_generator.py`

```python
class TaskGenerator:
    def generate_task_spec(
        self,
        ticker: str,                    # NEW: accept ticker
        risk_theme: str,
        years: List[int] | None = None
    ) -> TaskSpec:
        """
        Generate task from ticker + theme.
        
        If company not in pre-configured list:
          1. Lookup CIK from SEC EDGAR
          2. Auto-create CompanyConfig
          3. Generate TaskSpec
        
        Else (pre-configured):
          Use cached config (faster)
        """
```

This maintains backward compatibility:
- Pre-configured companies: Use cached config (fast)
- New tickers: Auto-lookup + cache (slightly slower, but works)

---

## Phase 3: Multi-Company Comparative Analysis (M5 Future)

**Future Enhancement** (after Phase 2 working):

```python
class SectorComparator:
    """Compare metrics across multiple companies"""
    
    def compare_sector(
        self,
        tickers: List[str],          # ["AAPL", "MSFT", "GOOGL"]
        risk_theme: str,             # "leverage_analysis"
        years: List[int]
    ) -> ComparativeReport:
        """
        Generate peer comparison report.
        
        Output:
          - Side-by-side metrics table
          - Trend analysis
          - Quartile ranking
          - LLM synthesis: "Among tech companies, Apple has..."
        """
```

---

## Testing Strategy

### Unit Tests (15+)

```python
# test_sec_integration.py
- test_cik_lookup_by_ticker
- test_cik_lookup_invalid_ticker
- test_company_info_fetch
- test_10k_fetch_success
- test_10k_fetch_missing_year
- test_xbrl_parse_metrics
- test_xbrl_unit_conversion
- test_xbrl_concept_mapping
- test_metric_extraction_accuracy (vs. real data)
- test_error_handling_network
- test_error_handling_company_not_found
```

### Integration Tests (10+)

```python
# test_universal_analyzer.py
- test_analyze_real_company_apple
- test_analyze_real_company_tesla
- test_analyze_real_company_microsoft
- test_analyze_multiple_years
- test_analyze_different_themes
- test_metric_accuracy_vs_sec_filing
- test_end_to_end_brief_generation
```

### Validation Tests

```python
# Verify extracted metrics match SEC filings
for company in [AAPL, MSFT, TSLA]:
    for year in [2023, 2024]:
        extracted = analyzer.extract_metrics(ticker, year)
        assert_matches_sec_filing(extracted)
```

---

## Success Criteria

### Phase 2 Complete (M5 Core)

- ✅ Accept any US stock ticker
- ✅ Auto-fetch real SEC 10-K XBRL data
- ✅ Extract 10+ financial metrics with >95% accuracy
- ✅ Generate verified brief for real company data
- ✅ Works for 5+ diverse companies (tech, automotive, finance, healthcare)
- ✅ 25+ tests, 100% passing
- ✅ No manual data configuration needed

### Metrics
```
Before M5: 
  Input: Company must be pre-configured
  Data: Mock/demo data only
  
After M5:
  Input: Any stock ticker (e.g., "NVDA", "JPM", "XOM")
  Data: Real SEC EDGAR XBRL
  Output: Verified brief with real metrics
  Coverage: 5000+ publicly traded US companies
```

---

## Deliverables

### Code
- `src/credit_research_agent/sec_integration.py` (400+ lines)
  - SECCompanyLookup
  - SEC10KFetcher
  - XBRLParser
  
- `src/credit_research_agent/universal_analyzer.py` (300+ lines)
  - UniversalCreditAnalyzer
  - AnalysisResult
  - Error handling

- Updated `src/credit_research_agent/task_generator.py` (100+ lines)
  - Auto-ticker lookup integration

- Enhanced `streamlit_app.py`
  - Real-time analysis mode
  - Ticker input widget
  - Live brief generation

### Tests
- `tests/test_sec_integration.py` (400+ lines, 15 tests)
- `tests/test_universal_analyzer.py` (300+ lines, 10 tests)

### Documentation
- M5 implementation guide
- XBRL concept mapping reference
- SEC EDGAR API documentation
- Error handling patterns

---

## Impact: From Framework to Product

### Before M5
```
Researcher: "Your system looks good, but can it work with my company?"
Me: "Not unless you pre-configure it first. It's a framework."
```

### After M5
```
Researcher: "Your system looks good, can it work with my company?"
Me: "Any US company. Just type the ticker."
demo.analyze(ticker="JPM", theme="leverage_analysis", years=[2023, 2024])
>>> "JPMorgan Chase - Leverage Analysis" (2-page verified brief)
```

---

## Timeline

| Phase | Component | Effort | Status |
|-------|-----------|--------|--------|
| 2.1 | SEC Lookup | 1 day | → |
| 2.2 | 10-K Fetcher | 1 day | → |
| 2.3 | XBRL Parser | 1.5 days | → |
| 2.4 | Analyzer | 1 day | → |
| 2.5 | TaskGen enhancement | 0.5 day | → |
| 2.6 | Streamlit UI | 0.5 day | → |
| Tests | Unit + Integration | 1 day | → |
| **Total** | **Phase 2 / M5 Core** | **6-7 days** | **→** |

---

**M5 transforms Verified Credit Research Agent from "specialized framework" to "universal product that works for any SEC company."**

This is production-grade software with real SEC data integration.
