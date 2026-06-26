import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.schemas import NumericClaim, NumericFact
from credit_research_agent.verification.fact_store import FactStore
from credit_research_agent.verification.numeric_verifier import verify_numeric_claim


def make_fact(
    fact_id: str,
    metric_name: str,
    fiscal_year: int,
    value: float,
    *,
    unit: str = "USD billions",
    confidence: str = "high",
    fact_source: str = "xbrl",
) -> NumericFact:
    return NumericFact(
        fact_id=fact_id,
        company="Ford Motor Company",
        ticker="F",
        fiscal_year=fiscal_year,
        metric_name=metric_name,
        display_name=metric_name.replace("_", " "),
        value=value,
        unit=unit,
        scale="billions",
        source_text="source excerpt",
        source_chunk_id=f"F_{fiscal_year}_10K_debt_001",
        source_url="https://www.sec.gov/Archives/example",
        filing_date=f"{fiscal_year + 1}-02-01",
        accession_number=f"0000037996-{str(fiscal_year + 1)[-2:]}-000001",
        extraction_method="xbrl_candidate_mapping",
        fact_source=fact_source,
        confidence=confidence,
        review_required=confidence != "high",
        source_detail={
            "source_classification": "xbrl_candidate" if fact_source == "xbrl" else "sentence_narrative",
            "selected_concept": "DebtLongtermAndShorttermCombinedAmountCompanyExcludingFordCredit",
            "candidate_concepts": [
                "DebtLongtermAndShorttermCombinedAmountCompanyExcludingFordCredit",
                "DebtAndCapitalLeaseObligationsOperatingSegmentsCompanyExcludingFordCredit",
            ],
            "raw_value": value * 1_000_000_000,
            "raw_unit": "USD",
        },
    )


def make_claim(
    claim_id: str = "claim_company_debt_2023_2025",
    metric_name: str = "company_debt_excluding_ford_credit",
    old_fact_id: str = "ford_2023_company_debt",
    new_fact_id: str = "ford_2025_company_debt",
    proposed_statement: str = "Company debt excluding Ford Credit increased from $19.944B in 2023 to $21.919B in 2025.",
) -> NumericClaim:
    return NumericClaim(
        claim_id=claim_id,
        metric_name=metric_name,
        claim_type="change_over_time",
        old_year=2023,
        new_year=2025,
        old_fact_id=old_fact_id,
        new_fact_id=new_fact_id,
        statement_template="{metric} changed from {old_value} in {old_year} to {new_value} in {new_year}.",
        proposed_statement=proposed_statement,
        required_calculations=["absolute_change", "percentage_change"],
    )


class NumericVerifierTest(unittest.TestCase):
    def test_verified_claim_computes_deterministic_change(self):
        store = FactStore()
        store.add_facts(
            [
                make_fact("ford_2023_company_debt", "company_debt_excluding_ford_credit", 2023, 19.944),
                make_fact("ford_2025_company_debt", "company_debt_excluding_ford_credit", 2025, 21.919),
            ]
        )

        result = verify_numeric_claim(make_claim(), store)

        self.assertEqual(result.status, "verified")
        self.assertEqual(result.direction, "increase")
        self.assertAlmostEqual(result.absolute_change, 1.975, places=6)
        self.assertEqual(result.percentage_change, 9.9)
        self.assertEqual(result.old_value, 19.944)
        self.assertEqual(result.new_value, 21.919)
        self.assertEqual([item["fact_id"] for item in result.evidence], ["ford_2023_company_debt", "ford_2025_company_debt"])

    def test_not_enough_data_when_comparison_year_fact_is_missing(self):
        store = FactStore()
        store.add_facts(
            [make_fact("ford_2023_company_debt", "company_debt_excluding_ford_credit", 2023, 19.944)]
        )

        result = verify_numeric_claim(make_claim(), store)

        self.assertEqual(result.status, "not_enough_data")
        self.assertIn("missing fact", " ".join(result.notes).lower())

    def test_low_confidence_fact_cannot_support_verified_claim(self):
        store = FactStore()
        store.add_facts(
            [
                make_fact("ford_2023_total_liquidity", "total_balance_sheet_cash_and_marketable_securities_restricted_cash", 2023, 40.4, fact_source="text"),
                make_fact(
                    "ford_2025_total_liquidity",
                    "total_balance_sheet_cash_and_marketable_securities_restricted_cash",
                    2025,
                    38.9,
                    confidence="low",
                    fact_source="text",
                ),
            ]
        )
        claim = make_claim(
            claim_id="claim_total_liquidity_2023_2025",
            metric_name="total_balance_sheet_cash_and_marketable_securities_restricted_cash",
            old_fact_id="ford_2023_total_liquidity",
            new_fact_id="ford_2025_total_liquidity",
            proposed_statement="Total balance sheet cash decreased from $40.4B in 2023 to $38.9B in 2025.",
        )

        result = verify_numeric_claim(claim, store)

        self.assertEqual(result.status, "low_confidence")
        self.assertIn("low confidence", " ".join(result.notes).lower())

    def test_inconsistent_when_fact_units_do_not_match(self):
        store = FactStore()
        store.add_facts(
            [
                make_fact("ford_2023_company_debt", "company_debt_excluding_ford_credit", 2023, 19.944, unit="USD billions"),
                make_fact("ford_2025_company_debt", "company_debt_excluding_ford_credit", 2025, 21919.0, unit="USD millions"),
            ]
        )

        result = verify_numeric_claim(make_claim(), store)

        self.assertEqual(result.status, "inconsistent")
        self.assertIn("unit mismatch", " ".join(result.notes).lower())

    def test_unsupported_when_claim_references_wrong_metric(self):
        store = FactStore()
        store.add_facts(
            [
                make_fact("ford_2023_current_debt", "company_debt_payable_within_one_year", 2023, 0.477),
                make_fact("ford_2025_current_debt", "company_debt_payable_within_one_year", 2025, 5.55),
            ]
        )
        claim = make_claim(
            metric_name="company_debt_excluding_ford_credit",
            old_fact_id="ford_2023_current_debt",
            new_fact_id="ford_2025_current_debt",
            proposed_statement="Company debt excluding Ford Credit increased from $0.477B in 2023 to $5.55B in 2025.",
        )

        result = verify_numeric_claim(claim, store)

        self.assertEqual(result.status, "unsupported")
        self.assertIn("metric mismatch", " ".join(result.notes).lower())


if __name__ == "__main__":
    unittest.main()
