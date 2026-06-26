# Debt and Liquidity Research Skill

When answering debt/liquidity risk questions over SEC filings:

required_evidence_categories:
- debt
- liquidity
- management_explanation
- numeric_facts

required_sections:
- Liquidity and Capital Resources
- Debt and Commitments
- Management's Discussion and Analysis

rules:
- verified_numeric_changes_must_appear_in_conclusions: true
- unsupported_numeric_claims_must_be_excluded: true

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
