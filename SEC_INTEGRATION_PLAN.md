# SEC Integration Plan: Universal Company Support

**Objective**: Enable system to accept ANY stock ticker → automatically fetch real SEC data → generate verified brief

**Timeline**: Aggressive (unlimited time, full focus)

---

## Current State vs. Target

### Before (Current)
```python
# 需要预配置的公司
TaskGenerator().generate_task_spec("apple", "leverage_analysis")
# ↑ 只能用已配置的4家公司
```

### After (Target)
```python
# 任意股票代码，自动工作
analyzer = SECAnalyzer()
brief = analyzer.analyze(ticker="TSLA", theme="solvency_assessment", years=[2023, 2024])
# ↑ 自动：查询CIK → 下载10-K → 解析XBRL → 提取指标 → 生成brief
```

---

## Phase 2: SEC Automation (New Work)

### 2.1 SEC EDGAR Integration (2-3 days)

**File**: `src/credit_research_agent/sec_integration.py`

**Components**:

```python
class SECCompanyLookup:
    """Query SEC EDGAR for company info"""
    def get_cik_by_ticker(ticker: str) -> str:
        # Call SEC.gov JSON API
        # https://www.sec.gov/files/company_tickers.json
        # Returns CIK
    
    def get_company_info(cik: str) -> CompanyInfo:
        # Fetch company metadata (name, industry, etc.)
        # from SEC EDGAR
        # Returns: name, sector, latest_10k_url

class SEC10KFetcher:
    """Download 10-K filings from SEC EDGAR"""
    def fetch_10k_xbrl(cik: str, fiscal_year: int) -> str:
        # Query SEC EDGAR for 10-K XBRL submissions
        # Download the XML file
        # Returns: raw XBRL XML content
    
    def fetch_10k_text(cic: str, fiscal_year: int) -> str:
        # Fetch narrative 10-K text
        # For fallback evidence extraction

class XBRLParser:
    """Parse XBRL 10-K filings"""
    def extract_metrics(xbrl_content: str, metric_names: List[str]) -> Dict[str, float]:
        # Parse XBRL XML
        # Extract specified metrics using XBRL context/unit logic
        # Handle unit conversions (millions → billions)
        # Returns: {metric_name: value} for each requested metric
    
    def extract_fiscal_year(xbrl_content: str) -> int:
        # Extract fiscal year from XBRL context
```

**Dependencies to Add**:
- `requests` (HTTP calls to SEC EDGAR)
- `xml.etree.ElementTree` (XBRL parsing)
- `lxml` (better XML handling)

**Tests**: 15+ unit tests
- CIK lookup by ticker
- 10-K URL retrieval
- XBRL parsing
- Metric extraction accuracy
- Unit conversion (M→B)
- Error handling (ticker not found, no filing, invalid XBRL)

### 2.2 Unified Analyzer (1-2 days)

**File**: `src/credit_research_agent/universal_analyzer.py`

**What it does**:

```python
class UniversalCreditAnalyzer:
    """Analyze any SEC-listed company"""
    
    def analyze(
        self,
        ticker: str,
        risk_theme: str,
        years: List[int]
    ) -> AnalysisResult:
        """
        Complete flow:
        1. Lookup CIK from ticker
        2. Fetch 10-K XBRL for each year
        3. Extract metrics
        4. Generate TaskSpec
        5. Create VerifiedMetricsSet
        6. Generate brief
        7. Return with trace
        """
```

**Flow**:
```
Input: ticker="TSLA", theme="leverage_analysis", years=[2023,2024]
    ↓
[SEC Lookup] Get TSLA's CIK (1318605)
    ↓
[Fetch 10-K] Download 2023 & 2024 10-K XBRL
    ↓
[Parse XBRL] Extract debt, equity, interest metrics
    ↓
[Task Generation] Create TaskSpec from config
    ↓
[Brief Generation] Generate markdown brief
    ↓
Output: 
{
  "company": "Tesla Inc.",
  "ticker": "TSLA",
  "theme": "leverage_analysis",
  "brief": "# Tesla Inc. — Debt-to-equity...",
  "metrics": [...],
  "trace": [...]
}
```

**Tests**: 10+ integration tests
- End-to-end for 3+ real companies
- Different themes (leverage, solvency, debt_liquidity)
- Error handling (invalid ticker, missing data)
- Metrics accuracy validation

### 2.3 Update TaskGenerator (0.5 days)

**Change**: Make it auto-generate company config if not exists

```python
# Before: only works with pre-configured companies
task = TaskGenerator().generate_task_spec("apple", "leverage_analysis")

# After: auto-lookup CIK if company not in config
task = TaskGenerator().generate_task_spec("tsla", "leverage_analysis")
# ↑ Auto-fetches TSLA's CIK, name, sector from SEC EDGAR
```

### 2.4 Streamlit Demo Enhancement (1 day)

**Update**: `streamlit_app.py`

Add interactive mode:
```python
# New page: "Real-Time Analysis"
ticker_input = st.text_input("Enter stock ticker (e.g., AAPL, MSFT, TSLA)")
theme_select = st.selectbox("Risk Theme", 
    ["debt_liquidity", "leverage_analysis", "solvency_assessment"])
years_select = st.slider("Years to compare", [2020, 2021, 2022, 2023, 2024])

if st.button("Analyze"):
    analyzer = UniversalCreditAnalyzer()
    result = analyzer.analyze(ticker, theme, [years_select[0], years_select[1]])
    st.markdown(result['brief'])
    st.json(result['metrics'])
```

**This enables**:
- Users can type ANY stock ticker
- System fetches real SEC data
- Generates real brief live

---

## Phase 3: M5 - Multi-Agent Reasoning (Future)

Once Phase 2 done, consider M5:

**M5: Multi-Company Comparative Analysis**

```python
# Example: Compare leverage across tech sector
comparator = SectorComparator(
    companies=["AAPL", "MSFT", "GOOGL", "NVDA"],
    theme="leverage_analysis",
    years=[2023, 2024]
)
report = comparator.generate_comparative_report()
# Output: "Among 4 tech companies, Apple has highest leverage (1.7x), 
#          Microsoft lowest (0.8x). Trends: ...
```

Would require:
- Comparative metrics calculation
- Peer benchmarking
- Trend analysis across companies
- LLM synthesis of cross-company patterns

---

## Summary

| Phase | Work | Days | Impact |
|-------|------|------|--------|
| 1 | Config system | 2 | Flexible architecture |
| 2 | SEC automation | 5-6 | **Universal support** |
| 3 | M5 comparisons | TBD | Production feature |

After Phase 2: **True product. Input any ticker, get verified analysis.**

---

## Key Files to Create/Modify

```
NEW:
  src/credit_research_agent/sec_integration.py     (300-400 lines)
  src/credit_research_agent/universal_analyzer.py  (200-300 lines)
  tests/test_sec_integration.py                    (300+ lines)
  tests/test_universal_analyzer.py                 (200+ lines)

MODIFY:
  src/credit_research_agent/task_generator.py      (add auto-lookup)
  streamlit_app.py                                 (add real-time mode)
```

---

## Success Criteria

✅ Input: Any US stock ticker  
✅ Process: Auto-fetch real SEC data  
✅ Output: Verified brief with real metrics  
✅ Tests: 25+ new tests, 100% pass  
✅ Demo: 5+ real companies working live

---

This transforms the project from "framework" to "product".
