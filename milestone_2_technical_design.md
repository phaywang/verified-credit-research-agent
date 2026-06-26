# Verified Credit Research Agent

## Milestone 2 Technical Design

Status: approved draft updated for M2a implementation  
Milestone boundary: M2a numeric verification first; M2b memory/skill after M2a acceptance

### Scope

Milestone 2 upgrades the working Milestone 1 retrieval loop into a verified credit research agent for the same narrow Ford debt/liquidity demo question:

> How did Ford's debt and liquidity risk change from 2023 to 2025, and what evidence supports the change?

Milestone 2 keeps the same company, years, filing corpus, and risk theme. It does not broaden the project into a general SEC chatbot.

Milestone 2 is split into two implementation slices.

M2a adds:

- Deterministic numeric verification.
- Numeric claim extraction and structured claim inventory.
- Unsupported numeric claim flagging.
- Workpaper additions for verified facts, claims, and evaluation metrics.
- Final brief upgrades where verified numeric changes are written back into the Debt Risk Changes and Liquidity Risk Changes sections.
- XBRL-first extraction for standard debt facts.
- Text extraction for only high-confidence narrative liquidity facts.

M2b adds, after M2a acceptance:

- Minimal research memory that affects query construction.
- One reusable debt/liquidity research skill.

Milestone 2 excludes:

- MCP server.
- Multi-company support.
- Multiple risk themes.
- Forecasting or investment recommendations.
- Full XBRL taxonomy coverage beyond the curated Ford debt concepts needed for this demo.
- Full RAGAS or LangSmith evaluation.
- Complex LLM-driven table understanding.

Core principle:

> The final answer may include numeric comparison conclusions only when they are supported by cited filing evidence and verified by deterministic Python tools.

---

## 1. Milestone 1 Baseline

Milestone 1 already provides:

- Ford 2023 and 2025 10-K ingestion.
- Section-aware chunks.
- BM25 + dense retrieval.
- RRF fusion.
- Local reranking.
- Evidence sufficiency check.
- Query rewrite and re-retrieval.
- Final cited evidence brief.
- Trace log and workpaper artifacts.

Milestone 1 intentionally avoids numeric conclusions. The current final answer cites evidence such as:

- 2023 liquidity disclosure showing total balance sheet cash/cash equivalents/marketable securities/restricted cash.
- 2025 liquidity disclosure showing the same metric.
- 2023 Debt and Commitments note.
- 2025 Debt and Commitments note.
- 2023 and 2025 credit facility evidence.

Milestone 2 turns those cited disclosures into verified analytical statements, for example:

```text
Ford's total balance sheet cash/cash equivalents/marketable securities/restricted cash decreased from $40.4B in 2023 to $38.9B in 2025, a $1.5B decline, verified from cited Liquidity and Capital Resources chunks.
```

The exact final wording must be generated only after verification passes.

---

## 2. Target File Structure

```text
verified-credit-research-agent/
  milestone_2_technical_design.md

  data/
    processed/
      ford_2023_2025_chunks.jsonl
      ford_2023_2025_verified_facts.json

  memory/
    research_memory.json

  skills/
    debt_liquidity_research/
      SKILL.md

  runs/
    ford_debt_liquidity_2023_2025/
      task.md
      task_spec.json
      plan.json
      retrieved_chunks.json
      reranked_chunks.json
      evidence_table.json
      evidence_coverage.json
      query_rewrites.json
      numeric_facts.json
      numeric_claims.json
      numeric_verification.json
      evaluation_summary.json
      critic_report.json
      trace_log.json
      final_answer.md
      memory_update.json

  src/
    credit_research_agent/
      verification/
        __init__.py
        fact_extractor.py
        fact_store.py
        numeric_claim_extractor.py
        numeric_verifier.py
        calculations.py

      memory/
        __init__.py
        research_memory.py

      skills/
        __init__.py
        skill_loader.py

      evaluation/
        __init__.py
        metrics.py

      agent/
        loop_controller.py
        synthesizer.py
        critic.py

  scripts/
    run_ford_demo.py
    inspect_numeric_verification.py

  tests/
    test_fact_extractor.py
    test_numeric_verifier.py
    test_numeric_claim_extractor.py
    test_research_memory.py
    test_skill_loader.py
    test_evaluation_metrics.py
```

### Notes

- `data/processed/ford_2023_2025_verified_facts.json` is optional cache output. The canonical run-specific fact record lives under `runs/.../numeric_facts.json`.
- `memory/research_memory.json` is small, explicit, and versionable.
- `skills/debt_liquidity_research/SKILL.md` is the only skill in Milestone 2.
- Existing Milestone 1 scripts remain valid; `scripts/run_ford_demo.py` gains verification-aware behavior.

---

## 3. Architecture Changes

Milestone 1 loop:

```text
PLAN
RETRIEVE
RERANK
EVIDENCE_CHECK
QUERY_REWRITE
RETRIEVE_AGAIN
SYNTHESIZE
CRITIC
FINALIZE
```

M2a loop:

```text
PLAN
RETRIEVE
RERANK
EVIDENCE_CHECK
QUERY_REWRITE
RETRIEVE_AGAIN
EXTRACT_NUMERIC_FACTS
PROPOSE_NUMERIC_CLAIMS
VERIFY_NUMERIC_CLAIMS
SYNTHESIZE
CRITIC
REPAIR
EVALUATE
FINALIZE
```

M2b inserts `READ_MEMORY`, `LOAD_SKILL`, and `UPDATE_MEMORY` after the M2a numeric verification loop is accepted.

### State Responsibilities

`READ_MEMORY` (M2b)

- Load prior Ford debt/liquidity useful sections and successful queries.
- Add memory-derived hints to the plan and initial query.

`LOAD_SKILL` (M2b)

- Load the debt/liquidity research rules from `skills/debt_liquidity_research/SKILL.md`.
- Enforce required evidence categories, year coverage, and numeric verification rules.

`EXTRACT_NUMERIC_FACTS`

- Extract known Ford debt/liquidity metrics from two fact-source families:
  - XBRL-first structured facts for standard debt metrics.
  - Text evidence for high-confidence narrative liquidity metrics.
- Store facts with metric name, year, value, unit, source chunk, and confidence.

`PROPOSE_NUMERIC_CLAIMS`

- Generate structured candidate claims from verified-ready fact pairs.
- This can be deterministic in Milestone 2.

`VERIFY_NUMERIC_CLAIMS`

- Use deterministic calculations for deltas and percentage changes.
- Mark each claim as verified, unsupported, inconsistent, or not enough data.

`SYNTHESIZE`

- Upgrade the final brief from evidence list to verified analysis.
- Only verified numeric changes can appear as conclusion sentences.

`CRITIC`

- Check citation coverage and numeric verification coverage.
- Remove or downgrade unsupported numeric claims.

`EVALUATE`

- Compute citation coverage, numeric validation rate, unsupported claim count, and evidence coverage metrics.

`UPDATE_MEMORY` (M2b)

- Persist useful sections, successful rewrite queries, failed queries, and evidence paths.

---

## 4. Numeric Verification Strategy

M2a verifies a curated set of debt/liquidity facts needed for the Ford demo. It does not attempt broad financial statement analysis, but it does use XBRL where XBRL is the most reliable source.

### 4.1 Fact Sources

Facts come from metric-specific source families:

1. XBRL structured facts for standard debt metrics.
2. Retrieved SEC filing chunks for source citations and liquidity narrative facts.
3. Existing section-aware chunk metadata for fiscal year, section type, filing date, and accession number.

Debt facts must be XBRL-first because Ford's debt tables are flattened in SEC HTML text and are brittle under regex extraction.

Liquidity facts must be source-classified before extraction:

- Sentence-level liquidity facts with clear year and amount can be parsed by text regex and marked high confidence.
- Table-derived liquidity facts must not be assumed reliable. If a metric appears only in a flattened table, the extractor must either locate an XBRL concept for it or mark the fact low confidence / review required and exclude it from final conclusions.
- The first high-confidence liquidity target is total balance sheet cash/cash equivalents/marketable securities/restricted cash because it appears in narrative disclosure text for both 2023 and 2025.

### 4.2 Initial Fact Set

The first verified facts should cover:

Liquidity:

- `total_balance_sheet_cash_and_marketable_securities_restricted_cash`
- `company_cash` only if source classification confirms a reliable sentence-level disclosure or XBRL equivalent.
- `company_liquidity` only if source classification confirms a reliable sentence-level disclosure or XBRL equivalent.
- `ford_credit_net_liquidity_available_for_use` only if source classification confirms a reliable sentence-level disclosure or XBRL equivalent.
- `ford_credit_liquidity_sources` only if source classification confirms a reliable sentence-level disclosure or XBRL equivalent.
- `ford_credit_committed_capacity` if parsed from clear credit facility narrative sentence.

Debt:

- `company_debt_excluding_ford_credit`
- `company_debt_payable_within_one_year`
- `company_long_term_debt_payable_after_one_year`
- `company_short_term_borrowings`
- `company_debt_maturities_next_twelve_months` is deferred unless total-bucket XBRL mapping is validated. Component-only XBRL concepts must not be used as total maturity facts.
- `ford_credit_total_debt` only if XBRL candidate mapping is validated.
- `total_debt_maturities_company_excluding_ford_credit` only if XBRL candidate mapping is validated.
- `total_debt_maturities_ford_credit` only if XBRL candidate mapping is validated.

Management explanation:

- Narrative snippets from MD&A that explain funding, liquidity profile, capital resources, or debt management.

### 4.3 XBRL-First Debt Extraction

Debt extraction uses an explicit candidate concept registry:

```python
DEBT_XBRL_CONCEPT_CANDIDATES = {
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
```

Rules:

- Candidate order is priority order.
- The extractor selects the first candidate with a value for the target fiscal year.
- The selected concept name is persisted on `NumericFact.source_detail.selected_concept`.
- All attempted concepts are persisted on `NumericFact.source_detail.candidate_concepts`.
- XBRL values are normalized to USD billions for comparison display while preserving raw USD values.
- XBRL facts still need filing citations. The fact store should attach the corresponding debt chunk citation for the year and metric scope, usually the `Debt and Commitments` chunk that contains the human-readable table.
- If no candidate has a value, the fact is not fabricated from flattened table text. It is recorded as missing or unsupported.

Validated Ford examples:

| Metric | 2023 selected XBRL value | 2025 selected XBRL value |
|---|---:|---:|
| `company_debt_excluding_ford_credit` | `$19.944B` | `$21.919B` |
| `company_debt_payable_within_one_year` | `$0.477B` | `$5.550B` |
| `company_long_term_debt_payable_after_one_year` | `$19.467B` | `$16.369B` |
| `company_short_term_borrowings` | `$0.362B` | `$1.355B` |

Deferred Ford example:

- `company_debt_maturities_next_twelve_months` has component XBRL concepts, but the first validated extraction found a corporate debt securities bucket rather than the total company excluding Ford Credit bucket for 2025. It must remain excluded from verified conclusions until the total-bucket mapping is validated or the component-sum logic is explicitly implemented and tested.

### 4.4 Liquidity Fact Source Classification

Before extracting liquidity facts, classify the evidence source:

```text
sentence_narrative
table_flattened
xbrl_candidate
unknown
```

High confidence text extraction is allowed only when:

- The fact appears in a sentence or short paragraph, not only in a flattened table.
- The sentence contains the metric label, fiscal year or date, and dollar amount.
- The unit is explicit, such as "billion".
- The source chunk is a liquidity or credit facility section.

Example high-confidence narrative pattern:

```text
At December 31, 2025, total balance sheet cash, cash equivalents, marketable securities, and restricted cash was $38.9 billion.
```

Table-only liquidity metrics are handled conservatively:

- If `company_liquidity`, `company_cash`, or `Ford Credit net liquidity available for use` appears only in flattened rows, mark `confidence="low"` and `review_required=true` unless an XBRL equivalent is found.
- Low-confidence liquidity facts can appear in `numeric_facts.json` for analyst review but cannot support final conclusion sentences.

### 4.5 Fact Extraction Rules

Use deterministic, metric-specific extractors rather than general table understanding.

`Liquidity and Capital Resources` extractor:

- Locate sentence-level phrases such as:
  - `At December 31, 2023, total balance sheet cash... was $40.4 billion`
  - `At December 31, 2025, total cash... was $38.9 billion`
- Classify `Company Cash`, `Company liquidity`, and `Ford Credit net liquidity available for use` as table-derived unless a clear sentence or XBRL concept is found.
- Normalize all values to USD billions unless source unit says otherwise.

`Debt and Commitments` extractor:

- Use XBRL candidate concept mapping first.
- Attach the matching debt note chunk as citation support.
- Do not parse flattened debt table rows for verified facts.

`Total Debt Maturities` extractor:

- Use XBRL maturity concepts when available.
- Preserve maturity bucket labels and selected concept names.
- Do not infer maturity buckets from flattened text order.

`Credit Facilities` extractor:

- Locate clear narrative phrases such as:
  - `Ford Credit's committed capacity totaled $45.3 billion`
  - `Ford Credit's committed capacity totaled $45.1 billion`
- Treat table-only `net liquidity available for use` and `liquidity sources` facts as review-required unless an XBRL equivalent is validated.

### 4.6 Parsing Reliability Tiers

Each extracted fact should carry a reliability tier:

```json
{
  "extraction_method": "xbrl_candidate_mapping | narrative_regex | table_regex_review_only",
  "confidence": "high | medium | low",
  "review_required": false
}
```

High confidence:

- Sentence-level metric with clear year and dollar amount.
- XBRL fact selected from a validated candidate concept for the requested metric/year.

Medium confidence:

- Table text is flattened but row label and year/value order are clear, used only for workpaper review.

Low confidence:

- Ambiguous table text, multiple nearby values, or unclear unit.

Low-confidence facts should not support final numeric conclusions unless manually reviewed or separately confirmed.

---

## 5. Data Schemas

Use Pydantic models consistent with Milestone 1.

### 5.1 NumericFact

```json
{
  "fact_id": "ford_2025_company_liquidity",
  "company": "Ford Motor Company",
  "ticker": "F",
  "fiscal_year": 2025,
  "metric_name": "company_liquidity",
  "display_name": "Company liquidity",
  "value": 49.8,
  "unit": "USD billions",
  "scale": "billions",
  "source_text": "Company excluding Ford Credit ... Liquidity 46.7 49.8",
  "source_chunk_id": "F_2025_10K_liquidity_001",
  "source_url": "https://www.sec.gov/Archives/...",
  "filing_date": "2026-02-11",
  "accession_number": "0000037996-26-000015",
  "extraction_method": "narrative_regex",
  "fact_source": "text",
  "confidence": "high",
  "review_required": false,
  "source_detail": {
    "source_classification": "sentence_narrative",
    "selected_concept": null,
    "candidate_concepts": [],
    "raw_value": 38.9,
    "raw_unit": "USD billions"
  }
}
```

XBRL debt example:

```json
{
  "fact_id": "ford_2025_company_debt_payable_within_one_year",
  "company": "Ford Motor Company",
  "ticker": "F",
  "fiscal_year": 2025,
  "metric_name": "company_debt_payable_within_one_year",
  "display_name": "Company debt payable within one year excluding Ford Credit",
  "value": 5.55,
  "unit": "USD billions",
  "scale": "billions",
  "source_text": "Total debt payable within one year 1,756 5,550",
  "source_chunk_id": "F_2025_10K_debt_008",
  "source_url": "https://www.sec.gov/Archives/...",
  "filing_date": "2026-02-11",
  "accession_number": "0000037996-26-000015",
  "extraction_method": "xbrl_candidate_mapping",
  "fact_source": "xbrl",
  "confidence": "high",
  "review_required": false,
  "source_detail": {
    "source_classification": "xbrl_candidate",
    "selected_concept": "LongTermDebtCurrentCompanyExcludingFordCredit",
    "candidate_concepts": [
      "LongTermDebtCurrentCompanyExcludingFordCredit",
      "LongTermDebtCurrentOperatingSegmentsCompanyExcludingFordCredit"
    ],
    "raw_value": 5550000000,
    "raw_unit": "USD"
  }
}
```

### 5.2 NumericClaim

```json
{
  "claim_id": "claim_company_liquidity_2023_2025",
  "metric_name": "company_liquidity",
  "claim_type": "change_over_time",
  "old_year": 2023,
  "new_year": 2025,
  "old_fact_id": "ford_2023_company_liquidity",
  "new_fact_id": "ford_2025_company_liquidity",
  "statement_template": "Company liquidity changed from {old_value} in {old_year} to {new_value} in {new_year}.",
  "proposed_statement": "Company liquidity increased from $46.4B in 2023 to $49.8B in 2025.",
  "required_calculations": ["absolute_change", "percentage_change"]
}
```

### 5.3 NumericVerificationResult

```json
{
  "claim_id": "claim_company_liquidity_2023_2025",
  "claim": "Company liquidity increased from $46.4B in 2023 to $49.8B in 2025.",
  "status": "verified",
  "metric_name": "company_liquidity",
  "old_year": 2023,
  "new_year": 2025,
  "old_value": 46.4,
  "new_value": 49.8,
  "unit": "USD billions",
  "absolute_change": 3.4,
  "percentage_change": 7.33,
  "direction": "increase",
  "evidence": [
    {
      "year": 2023,
      "fact_id": "ford_2023_company_liquidity",
      "source_chunk_id": "F_2023_10K_liquidity_001",
      "source_url": "https://www.sec.gov/Archives/..."
    },
    {
      "year": 2025,
      "fact_id": "ford_2025_company_liquidity",
      "source_chunk_id": "F_2025_10K_liquidity_001",
      "source_url": "https://www.sec.gov/Archives/..."
    }
  ],
  "notes": "Values parsed from Liquidity and Capital Resources table. Percentage change rounded to two decimals."
}
```

Status values:

- `verified`
- `unsupported`
- `inconsistent`
- `not_enough_data`
- `low_confidence`

### 5.4 ResearchMemory

```json
{
  "Ford": {
    "debt_liquidity": {
      "useful_sections": [
        "Liquidity and Capital Resources",
        "Debt and Commitments",
        "Total Debt Maturities",
        "Management's Discussion and Analysis",
        "Committed Credit Facilities"
      ],
      "successful_queries": [
        "Ford 2023 2025 10-K debt long-term debt debt maturities debt and commitments company debt excluding Ford Credit liquidity capital resources"
      ],
      "failed_queries": [
        "Ford 2023 10-K liquidity cash credit facilities"
      ],
      "prior_evidence_paths": [
        "runs/ford_debt_liquidity_2023_2025/evidence_table.json"
      ],
      "verified_metrics": [
        "company_liquidity",
        "company_debt_excluding_ford_credit"
      ],
      "last_updated": "2026-06-26T..."
    }
  }
}
```

Memory must affect behavior:

- Planner should include useful section names in initial query.
- Query rewriter should prefer successful query patterns for missing evidence.
- Retrieval should optionally boost previously useful sections.

---

## 6. Component Interfaces

### 6.1 Fact Extractor

Module: `verification/fact_extractor.py`

```python
def extract_numeric_facts(evidence: list[EvidenceChunk]) -> list[NumericFact]:
    ...
```

Responsibilities:

- Extract only supported debt/liquidity metrics from selected evidence chunks and XBRL payloads.
- Keep source chunk IDs and source URLs.
- Normalize units.
- Assign confidence and review flags.
- Use candidate concept mapping for XBRL debt facts.
- Classify liquidity source reliability before extracting table-adjacent values.

Non-goals:

- Full table extraction.
- Full XBRL taxonomy mapping.
- Guessing values when table text is ambiguous.

### 6.2 Fact Store

Module: `verification/fact_store.py`

```python
class FactStore:
    def add_facts(self, facts: list[NumericFact]) -> None: ...
    def get_fact(self, metric_name: str, fiscal_year: int) -> NumericFact | None: ...
    def get_pair(self, metric_name: str, old_year: int, new_year: int) -> tuple[NumericFact, NumericFact] | None: ...
```

Responsibilities:

- Deduplicate facts by metric/year/source.
- Prefer high-confidence facts.
- Prefer XBRL facts over text facts for standard debt metrics.
- Respect candidate concept priority when more than one XBRL fact is available.
- Provide fact pairs for claim generation.

### 6.3 Numeric Claim Extractor

Module: `verification/numeric_claim_extractor.py`

```python
def propose_numeric_claims(task_spec: TaskSpec, fact_store: FactStore) -> list[NumericClaim]:
    ...
```

Responsibilities:

- Generate candidate comparison claims for metric pairs.
- Do this deterministically for Milestone 2.
- Only propose claims when both comparison years have acceptable facts.

Initial claim types:

- `change_over_time`
- `availability_change`
- `debt_level_change`

### 6.4 Calculations

Module: `verification/calculations.py`

```python
def calculate_change(old_value: float, new_value: float) -> float:
    ...

def calculate_percentage_change(old_value: float, new_value: float) -> float | None:
    ...

def direction(old_value: float, new_value: float) -> str:
    ...
```

Rules:

- Round display values consistently.
- Do not divide by zero.
- Preserve raw values in JSON.

### 6.5 Numeric Verifier

Module: `verification/numeric_verifier.py`

```python
def verify_numeric_claim(claim: NumericClaim, fact_store: FactStore) -> NumericVerificationResult:
    ...

def verify_numeric_claims(claims: list[NumericClaim], fact_store: FactStore) -> list[NumericVerificationResult]:
    ...
```

Responsibilities:

- Confirm required facts exist.
- Confirm year pairing and units match.
- Compute changes deterministically.
- Return structured verification result.

### 6.6 Research Memory

Module: `memory/research_memory.py`

```python
class ResearchMemory:
    def load(self) -> None: ...
    def get_topic_memory(self, company: str, risk_theme: str) -> TopicMemory: ...
    def update_from_run(self, run_artifacts: RunArtifacts) -> MemoryUpdate: ...
    def save(self) -> None: ...
```

Responsibilities:

- Persist useful sections.
- Persist successful and failed queries.
- Persist prior evidence paths.
- Influence planner/retriever behavior.

### 6.7 Skill Loader

Module: `skills/skill_loader.py`

```python
def load_debt_liquidity_skill(path: Path) -> ResearchSkill:
    ...
```

Responsibilities:

- Load the single skill file.
- Parse required sections and rules in a lightweight way.
- Make skill requirements available to evidence checker and synthesizer.

### 6.8 Evaluation Metrics

Module: `evaluation/metrics.py`

```python
def compute_evaluation_summary(
    final_answer: FinalAnswer,
    evidence: list[EvidenceChunk],
    verification_results: list[NumericVerificationResult],
    coverage: EvidenceCoverage
) -> EvaluationSummary:
    ...
```

Metrics:

- `citation_coverage`
- `numeric_validation_rate`
- `unsupported_claim_count`
- `verified_numeric_claim_count`
- `evidence_coverage_by_year`
- `evidence_coverage_by_section`
- `memory_updated`

---

## 7. Skill File

Create:

```text
skills/debt_liquidity_research/SKILL.md
```

Content:

```markdown
# Debt and Liquidity Research Skill

When answering debt/liquidity risk questions over SEC filings:

1. Identify the company, fiscal years, filing types, and risk theme.
2. Retrieve evidence from:
   - Liquidity and Capital Resources
   - MD&A
   - Debt notes
   - Risk Factors
   - Credit facilities
   - Contractual obligations or debt maturity discussion
3. Ensure both comparison years are covered.
4. Separate management explanation from numeric evidence.
5. Verify all numeric claims using deterministic Python tools.
6. Do not state that risk improved or deteriorated unless both years have supporting evidence and the numeric claim is verified.
7. If evidence is incomplete, rewrite the query and retrieve again.
8. Final answer must include citations and limitations.
9. Final Debt Risk Changes and Liquidity Risk Changes sections must use verified numeric results when available.
10. Unsupported numeric claims must be excluded from final conclusions.
```

Skill must affect behavior:

- Evidence checker reads required evidence categories.
- Synthesizer checks the rule that verified numeric changes must be used in the final analytical sections.
- Critic uses the unsupported numeric claim rule.

---

## 8. Final Answer Upgrade

Milestone 1 final answer sections remain, but M2 changes their content.

### 8.1 Debt Risk Changes

Milestone 1:

```text
2023 debt evidence: [quoted evidence]
2025 debt evidence: [quoted evidence]
```

Milestone 2:

```text
Company debt excluding Ford Credit increased from $X in 2023 to $Y in 2025, a $Z increase, verified from Ford's Debt and Commitments note. [2023 citation] [2025 citation]
```

If verification fails:

```text
The retrieved Debt and Commitments notes contain debt disclosures for both years, but the system did not verify a comparable debt metric. The final conclusion excludes a debt-change claim pending analyst review.
```

### 8.2 Liquidity Risk Changes

Milestone 1:

```text
2023 liquidity evidence: [quoted evidence]
2025 liquidity evidence: [quoted evidence]
```

Milestone 2:

```text
Total balance sheet cash/cash equivalents/marketable securities/restricted cash decreased from $X in 2023 to $Y in 2025, a $Z decrease, verified from Liquidity and Capital Resources disclosures. [2023 citation] [2025 citation]
```

Also include company liquidity only if extracted from a validated high-confidence source:

```text
Company liquidity changed from $X to $Y, verified from the Company excluding Ford Credit liquidity table.
```

### 8.3 Management Explanation

Must use MD&A narrative chunks only.

Numeric tables cannot satisfy management explanation coverage.

### 8.4 Key Numeric Changes

Add a concise table:

```text
| Metric | 2023 | 2025 | Change | Status | Sources |
|---|---:|---:|---:|---|---|
| Total balance sheet cash/marketable securities/restricted cash | $40.4B | $38.9B | -$1.5B | verified | ... |
| Company liquidity | $46.4B | $49.8B | +$3.4B | verified | ... |
| Company debt excluding Ford Credit | $19.9B | $21.9B | +$2.0B | verified | ... |
```

Only include rows with verified or clearly flagged status.

---

## 9. Unsupported Claim Policy

Milestone 2 critic must reject:

- Numeric claims without source facts.
- Numeric claims with only one year of data.
- Numeric claims where units do not match.
- Derived percentage or absolute changes not produced by deterministic tools.
- Claims that say risk improved or deteriorated without verified supporting metrics.

Unsupported numeric claims should be written to `numeric_verification.json` and `critic_report.json`, but excluded from `final_answer.md` conclusion sections.

---

## 10. Trace Log Additions

Add these step types:

```text
READ_MEMORY
LOAD_SKILL
EXTRACT_NUMERIC_FACTS
PROPOSE_NUMERIC_CLAIMS
VERIFY_NUMERIC_CLAIMS
EVALUATE
UPDATE_MEMORY
```

Example trace steps:

```json
{
  "state": "EXTRACT_NUMERIC_FACTS",
  "timestamp": "...",
  "summary": "Extracted debt and liquidity facts from selected evidence chunks.",
  "outputs": {
    "numeric_facts_path": "runs/ford_debt_liquidity_2023_2025/numeric_facts.json"
  },
  "metrics": {
    "facts_extracted": 12,
    "high_confidence_facts": 9,
    "review_required_facts": 1
  }
}
```

```json
{
  "state": "VERIFY_NUMERIC_CLAIMS",
  "timestamp": "...",
  "summary": "Verified candidate numeric comparison claims.",
  "outputs": {
    "numeric_verification_path": "runs/ford_debt_liquidity_2023_2025/numeric_verification.json"
  },
  "metrics": {
    "verified_claims": 4,
    "unsupported_claims": 1,
    "numeric_validation_rate": 0.8
  }
}
```

Final metrics:

```json
{
  "citation_coverage": 1.0,
  "numeric_validation_rate": 0.8,
  "verified_numeric_claim_count": 4,
  "unsupported_claim_count": 1,
  "evidence_coverage_passed": true,
  "memory_updated": true
}
```

---

## 11. Workpaper Artifacts

Add:

### `numeric_facts.json`

All extracted numeric facts with source chunk IDs and confidence.

### `numeric_claims.json`

Candidate numeric claims proposed from fact pairs.

### `numeric_verification.json`

Verification results with calculations, source facts, and status.

### `evaluation_summary.json`

Simple metrics for interview/demo review.

### `memory_update.json`

What memory changed because of the run.

---

## 12. Build Order

### 12.1 M2a: Numeric Verification Core

1. Update M2 schemas:
   - `NumericFact`
   - `NumericClaim`
   - `NumericVerificationResult`
   - `EvaluationSummary`
2. Write tests first for:
   - deterministic calculations.
   - numeric verifier statuses: `verified`, `unsupported`, `inconsistent`, `not_enough_data`, `low_confidence`.
   - derived absolute and percentage changes.
3. Implement deterministic calculation utilities.
4. Implement numeric verifier.
5. Implement XBRL candidate concept registry for debt metrics.
6. Implement XBRL-first debt fact extraction.
7. Implement liquidity source classification.
8. Implement high-confidence narrative liquidity fact extraction.
9. Implement review-only handling for flattened liquidity table facts.
10. Implement fact store and deduplication:
   - prefer high-confidence facts.
   - prefer XBRL facts for debt.
   - preserve selected/candidate concepts.
11. Run fact extraction inspection and stop for reviewer validation:
   - `numeric_facts.json`
   - extracted debt facts from XBRL.
   - extracted liquidity facts from text.
   - source/confidence flags.
12. Implement deterministic claim proposal from fact pairs.
13. Add loop states for fact extraction and verification.
14. Update synthesizer so verified numeric results become conclusion sentences.
15. Update critic to reject unsupported numeric claims.
16. Add evaluation summary.
17. Run full demo and inspect:
    - `final_answer.md`
    - `numeric_facts.json`
    - `numeric_verification.json`
    - `evaluation_summary.json`
    - `trace_log.json`

### 12.2 M2b: Memory and Skill

After M2a acceptance:

1. Add memory schemas:
   - `TopicMemory`
   - `MemoryUpdate`
2. Create the debt/liquidity skill file.
3. Implement skill loader.
4. Implement research memory load/save.
5. Modify planner/query construction to use memory and skill hints.
6. Update evidence checker and synthesizer to consume skill rules.
7. Add memory update at end of run.
8. Run full demo and inspect:
   - `memory/research_memory.json`
   - `memory_update.json`
   - trace steps for `READ_MEMORY`, `LOAD_SKILL`, `UPDATE_MEMORY`

---

## 13. Acceptance Criteria

Milestone 2 is complete when:

### Numeric Verification

- The system extracts at least three comparable numeric metrics across 2023 and 2025.
- At least one liquidity metric is verified.
- At least one debt metric is verified.
- Absolute changes are calculated deterministically.
- Percentage changes are calculated deterministically when denominator is nonzero.
- Unsupported or low-confidence numeric claims are excluded from final conclusion sections.

### Final Brief

- Debt Risk Changes includes at least one verified debt change conclusion or an explicit limitation if no comparable debt metric is verified.
- Liquidity Risk Changes includes at least one verified liquidity change conclusion.
- Key Numeric Changes includes a verification status table.
- Management explanation still uses MD&A narrative evidence, not numeric tables.
- Every numeric conclusion cites both source-year chunks.

### Memory (M2b)

- `memory/research_memory.json` exists.
- Memory records useful sections, successful queries, failed queries, and prior evidence paths.
- A later run uses memory to improve or seed retrieval.

### Skill (M2b)

- `skills/debt_liquidity_research/SKILL.md` exists.
- Skill rules affect evidence checking, verification requirements, or synthesis behavior.

### Workpapers

- Run workspace includes:
  - `numeric_facts.json`
  - `numeric_claims.json`
  - `numeric_verification.json`
  - `evaluation_summary.json`
  - `memory_update.json`
- `trace_log.json` records fact extraction, claim verification, evaluation, and memory update.

### Tests

Unit tests pass for:

- Fact extraction from representative liquidity text.
- Fact extraction from representative debt text.
- Unit normalization.
- Change and percentage calculations.
- Numeric verification status logic.
- Unsupported claim rejection.
- Research memory load/save/update.
- Skill loading.
- Evaluation metrics.

---

## 14. Risks and Simplifications

### Risk: SEC Tables Are Flattened

SEC table text may lose row/column structure.

Mitigation:

- Use XBRL-first extraction for standard debt facts.
- Use metric-specific parsers only after source classification.
- Store source text excerpts.
- Mark ambiguous facts as low confidence.
- Do not use low-confidence facts for final conclusions.

### Risk: Debt Scope Ambiguity

Ford has multiple debt scopes:

- Company excluding Ford Credit.
- Ford Credit debt.
- Consolidated debt.
- Debt maturities.

Mitigation:

- Treat each scope as a separate metric.
- Do not combine scopes.
- Make scope explicit in every claim.

### Risk: Liquidity Scope Ambiguity

Ford reports several liquidity concepts:

- Total balance sheet cash/cash equivalents/marketable securities/restricted cash.
- Company cash.
- Company liquidity.
- Ford Credit net liquidity available for use.
- Ford Credit liquidity sources.

Mitigation:

- Treat each as a separate metric.
- Avoid saying “liquidity improved/deteriorated” without specifying metric.

### Risk: False Precision

Derived percentage changes may imply precision beyond disclosure quality.

Mitigation:

- Round to one or two decimals.
- Preserve raw values in workpapers.
- Use plain language in final answer.

### Simplification: Deterministic Claim Proposal

Milestone 2 can propose claims from known metric pairs instead of asking an LLM to invent claims.

Reason:

- Safer.
- Testable.
- Better aligned with numeric verification rules.

### Simplification: JSON Memory

Use `memory/research_memory.json` rather than SQLite.

Reason:

- Small scope.
- Easy to inspect in interviews.
- Easy to version.

---

## 15. Definition of Done

Milestone 2 is done when a reviewer can run:

```bash
python3 scripts/run_ford_demo.py --force-rewrite-demo
```

and inspect:

```text
runs/ford_debt_liquidity_2023_2025/final_answer.md
runs/ford_debt_liquidity_2023_2025/numeric_facts.json
runs/ford_debt_liquidity_2023_2025/numeric_claims.json
runs/ford_debt_liquidity_2023_2025/numeric_verification.json
runs/ford_debt_liquidity_2023_2025/evaluation_summary.json
runs/ford_debt_liquidity_2023_2025/trace_log.json
memory/research_memory.json
skills/debt_liquidity_research/SKILL.md
```

The demo should show:

1. The agent retrieved evidence.
2. The agent detected missing evidence and rewrote the query.
3. The system extracted numeric facts from cited chunks.
4. Deterministic tools verified numeric change claims.
5. Verified numeric results were written back into the final brief.
6. Unsupported numeric claims were excluded or flagged.
7. Evaluation metrics and memory updates were saved.
