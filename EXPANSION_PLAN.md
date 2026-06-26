# Expansion Plan: Multi-Company, Multi-Risk-Theme Framework

**Goal**: Transform from "Ford debt/liquidity analyzer" → "Generalizable credit research framework"

**Scope**: 
- Add 2-3 companies (Apple, Microsoft, Tesla)
- Add 2-3 risk themes beyond debt/liquidity (leverage, coverage, solvency)
- Validate that architecture works across combinations

**Timeline**: 2-3 weeks

---

## Current State: Ford Hardcoding

### Hardcoded Points (need to eliminate)
```
1. config.py
   - DEFAULT_RUN_ID = "ford_debt_liquidity_2023_2025" (hardcoded)
   - FORD_COMPANY = "Ford Motor Company" (hardcoded)

2. planner.py
   - f"Ford {years} {filing_types} debt liquidity risk..."
   - Hardcoded query structure

3. synthesizer.py
   - Hardcoded metrics: company_debt_excluding_ford_credit
   - Hardcoded brief template (# Ford Debt and Liquidity Risk Brief)
   - Hardcoded narrative logic

4. evidence_checker.py
   - Hardcoded required_evidence_categories (debt, liquidity)
   - Hardcoded required_sections

5. query_rewriter.py
   - parts: ["Ford"] (hardcoded company name)
   - Hardcoded keywords for rewrite

6. skill/debt_liquidity_research/SKILL.md
   - Only debt_liquidity_research skill exists
```

### What's Flexible
```
✓ Retrieval pipeline (hybrid_retrieve, rerank)
✓ Numeric verification (verify_numeric_claim)
✓ Guardrails (numeric_guardrail_check)
✓ ReAct loop (works for any task)
✓ Trace structure (generic)
```

---

## Expansion Architecture

### New: Configuration System

```
configs/
├── companies.yaml          # Company metadata
├── risk_themes.yaml        # Risk theme definitions
├── metrics_mapping.yaml     # XBRL/text metric mappings
└── skills/
    ├── debt_liquidity_research/SKILL.md      (existing)
    ├── leverage_analysis/SKILL.md            (new)
    ├── solvency_assessment/SKILL.md          (new)
    └── cash_flow_coverage/SKILL.md           (new)
```

### New: Skill System

Each company/risk-theme combo has a skill:

```yaml
# configs/skills/leverage_analysis/SKILL.md
required_evidence_categories:
  - debt
  - equity
  - market_value
  - interest_expense

required_sections:
  - Consolidated Balance Sheet
  - Consolidated Statement of Income
  - MD&A

rules:
  - debt_to_equity_ratio_must_be_calculated
  - interest_coverage_must_be_verified
```

### New: Metric Registry

```python
# src/credit_research_agent/metrics/registry.py

METRICS = {
    "leverage": {
        "debt_to_equity": {
            "xbrl_paths": [
                "DebtAndEquitySourceOfCreditLine",
                "StockholdersEquity"
            ],
            "text_patterns": [
                r"debt.*equity.*ratio",
                r"total.*debt.*stockholders.*equity"
            ]
        },
        "debt_to_assets": {...},
        "interest_coverage": {...}
    },
    "solvency": {
        "current_ratio": {...},
        "quick_ratio": {...}
    },
    "debt_liquidity": {
        "debt_total": {...},  # (existing)
        "liquidity_cash": {...}  # (existing)
    }
}
```

---

## Implementation Plan

### Phase 1: Configuration & Abstraction (4-5 days)

**1.1 Create configuration system**
```python
# src/credit_research_agent/config.py (refactor)

@dataclass
class CompanyConfig:
    ticker: str
    name: str
    cik: str
    filing_types: List[str]  # e.g., ["10-K"]
    
@dataclass
class RiskThemeConfig:
    name: str
    required_evidence: List[str]
    required_sections: List[str]
    metrics: Dict[str, MetricDefinition]
    
# Load from configs/companies.yaml, configs/risk_themes.yaml
```

**1.2 Refactor static modules to use config**
- `planner.py`: Dynamic plan generation from config
- `evidence_checker.py`: Check evidence_categories from config
- `synthesizer.py`: Template-driven brief from metric results

**1.3 Create metric registry**
```python
# src/credit_research_agent/metrics/registry.py
registry = MetricRegistry.load_from_yaml("configs/metrics_mapping.yaml")
```

**Acceptance**: Single test company (Ford) works with new config system

---

### Phase 2: Add Leverage Analysis (3-4 days)

**2.1 Create leverage_analysis skill**
- Define required metrics: debt_to_equity, debt_to_assets, interest_coverage
- Define required sections: Balance Sheet, Income Statement, MD&A
- Define required years (same as debt_liquidity)

**2.2 Add leverage metrics to registry**
- Debt total (already have)
- Shareholders' equity (XBRL: StockholdersEquity)
- Interest expense (XBRL: InterestExpense)
- Calculate: debt/equity, debt/assets, interest coverage

**2.3 Create leverage synthesizer**
- Generic logic: take metric results → generate brief prose
- Template: "Leverage ratio X:1 indicates [analysis]"
- No Ford-specific hardcoding

**2.4 Test on Ford + Apple**
- Ford: familiar baseline
- Apple: first expansion test (verify architecture works)

**Acceptance**: Both Ford and Apple return valid leverage briefs with verified metrics

---

### Phase 3: Add Solvency Assessment (3-4 days)

**3.1 Create solvency_assessment skill**
- Required metrics: current_ratio, quick_ratio, working_capital_trend
- Required sections: Balance Sheet, Cash Flow Statement

**3.2 Add solvency metrics**
- Current assets, current liabilities → current_ratio
- (Current assets - inventory), current liabilities → quick_ratio
- Operating cash flow / current liabilities → cash_flow_ratio

**3.3 Create solvency synthesizer**
- Template: "Current ratio X.X suggests [analysis]"
- Multi-year trend analysis

**3.4 Test on Ford + Apple + Microsoft**
- Familiar + known + new data

**Acceptance**: All 3 companies return valid solvency briefs

---

### Phase 4: Multi-Company Data & Integration (2-3 days)

**4.1 Validate data availability**
- Apple 10-K (2024, 2023)
- Microsoft 10-K (2024, 2023)
- Tesla 10-K (2024, 2023)

**4.2 Run end-to-end tests**
```
For each (company, risk_theme) in [
    (Ford, debt_liquidity),
    (Ford, leverage),
    (Ford, solvency),
    (Apple, debt_liquidity),
    (Apple, leverage),
    (Apple, solvency),
    (Microsoft, leverage),
    (Microsoft, solvency),
]:
  - Generate task spec
  - Run M3 ReAct agent
  - Verify guardrails pass
  - Document results
```

**4.3 Create comparative analysis example**
```
Compare leverage across: Ford, Apple, Microsoft
→ Show architecture handles heterogeneous comparisons
```

---

### Phase 5: Documentation & Demo (2 days)

**5.1 Update README**
- Architecture now supports N companies × M risk themes
- Show how to add new company: 3 simple steps
- Show how to add new risk theme: define metrics + skill

**5.2 Create expansion guide**
```markdown
## Adding a New Company

1. Add to configs/companies.yaml
2. Ingest SEC filings (scripts/ingest_company.py)
3. Test with any risk theme

## Adding a New Risk Theme

1. Define metrics in configs/metrics_mapping.yaml
2. Create skill in configs/skills/YOUR_THEME/SKILL.md
3. Test on any company
```

**5.3 Package new demo artifacts**
- examples/multi_company/apple_leverage.md
- examples/multi_company/microsoft_solvency.md
- examples/comparison/leverage_across_companies.md

---

## Key Design Decisions

### 1. Config-First Architecture
- **Why**: Eliminate company/risk-theme hardcoding
- **How**: YAML configs + dataclass-based loading
- **Benefit**: Adding new company/theme doesn't require code changes

### 2. Skill-Based Evidence Checking
- **Why**: Different risk themes have different evidence requirements
- **How**: Each risk theme has a SKILL.md (like debt_liquidity)
- **Benefit**: Evidence checker becomes generic (reads from skill)

### 3. Metric Registry Pattern
- **Why**: XBRL/text patterns vary by metric, company, time
- **How**: Central registry + pluggable extractors
- **Benefit**: Add new metric without touching verification code

### 4. Template-Driven Synthesis
- **Why**: Brief generation has patterns
- **How**: Metrics → structured results → template fill
- **Benefit**: Synthesis works for any risk theme

### 5. ReAct Loop Unchanged
- **Why**: It already works for any task
- **How**: Planner generates task-specific plan from config
- **Benefit**: M3 agent needs zero changes

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| SEC filing data missing for Apple/Microsoft | Use public EDGAR API; pre-download if needed |
| XBRL field names differ by company | Metric registry maps [company, metric] → [xbrl_paths] |
| New risk theme needs new extraction logic | Plugin system for extractors (text, XBRL, calculation) |
| Configuration bloat | Start minimal, add only what's needed for 3 themes |
| Tests take too long | Mock Bedrock for config validation tests |

---

## Validation Criteria

### ✅ Architecture Validation
- [ ] Ford + Apple + Microsoft all work with **existing M3 code**
- [ ] Adding new company requires **zero code changes** (config only)
- [ ] Adding new risk theme requires **no agent code changes**

### ✅ Quality Validation
- [ ] All new briefs pass numeric guardrails
- [ ] All briefs are deterministic (same inputs → same verified numbers)
- [ ] Trace logs show reasoning for all companies/themes

### ✅ Documentation Validation
- [ ] "How to add a company" is <1 page
- [ ] "How to add a risk theme" is <1 page
- [ ] Examples cover ≥2 companies × ≥2 risk themes

---

## Timeline

| Phase | Work | Duration | Status |
|-------|------|----------|--------|
| 1 | Configuration system | 4-5 days | →▶️ |
| 2 | Leverage analysis | 3-4 days | →▶️ |
| 3 | Solvency assessment | 3-4 days | →▶️ |
| 4 | Multi-company integration | 2-3 days | →▶️ |
| 5 | Documentation & demo | 2 days | →▶️ |
| | **TOTAL** | **14-18 days** | |

**Start**: Now  
**Target Completion**: 2-3 weeks

---

## Success Definition

**Before Expansion**:
> "Verified Credit Research Agent is a Ford debt/liquidity analyzer."

**After Expansion**:
> "Verified Credit Research Agent is a configurable, multi-company credit research framework.
> Architecture is validated on Ford/Apple/Microsoft × debt/leverage/solvency combinations.
> New companies/risk themes require only configuration, no code changes."

---

This plan transforms the project from demo-ware into a **generalizable framework** with proven extensibility. 
That's resume-competitive. 💪
