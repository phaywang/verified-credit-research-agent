# Debt and Liquidity Research Skill

When answering debt/liquidity risk questions over SEC filings:

## Required Evidence

**Categories**:
- debt
- liquidity
- management_explanation
- numeric_facts

**Sections**:
- Consolidated Balance Sheet
- Consolidated Statement of Cash Flows
- Liquidity and Capital Resources
- Debt and Commitments
- Management's Discussion and Analysis

## Key Metrics

- Total debt (company debt excluding subsidiaries like Ford Credit)
- Current debt (short-term, payable within 1 year)
- Long-term debt (payable after 1 year)
- Cash and cash equivalents
- Available liquidity (credit lines + cash)

## Research Steps

1. Identify the company, fiscal years, filing types, and risk theme.
2. Retrieve evidence from the required sections.
3. Ensure both comparison years are covered.
4. Separate management explanation from numeric evidence.
5. Verify all numeric claims using deterministic Python tools.
6. Do not state that risk improved or deteriorated unless both years have supporting evidence and the numeric claim is verified.
7. If evidence is incomplete, rewrite the query and retrieve again.
8. Final answer must include citations and limitations.
9. Final Debt Risk Changes and Liquidity Risk Changes sections must use verified numeric results when available.
10. Unsupported numeric claims must be excluded from final conclusions.

## Scoring Criteria

- Evidence completeness: both years present for both debt and liquidity
- Numeric verification: key metrics verified via XBRL or text extraction
- Citations: evidence linked back to specific filings and sections
- Limitations: caveats noted (e.g., "off-balance-sheet obligations not included")
