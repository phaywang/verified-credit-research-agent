"""Tests for deterministic metric resolution over XBRL inventory."""

import unittest

from credit_research_agent.metric_resolver import MetricResolver
from credit_research_agent.xbrl_inventory import XBRLFactInventoryBuilder


def _companyfacts_for_concepts(concepts):
    return {
        "facts": {
            "us-gaap": {
                concept: {
                    "units": {
                        "USD": [
                            {
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-01",
                                "end": "2025-12-31",
                                "val": value,
                            }
                        ]
                    }
                }
                for concept, value in concepts.items()
            }
        }
    }


class MetricResolverTest(unittest.TestCase):
    """Test resolver decisions and rejected alternates."""

    def setUp(self):
        self.resolver = MetricResolver()

    def _inventory(self, concepts):
        return XBRLFactInventoryBuilder().build(
            _companyfacts_for_concepts(concepts),
            2025,
        )

    def test_configured_concept_match_wins(self):
        inventory = self._inventory({"InterestExpense": 338000000})

        resolution = self.resolver.resolve(
            "interest_expense",
            inventory,
            ["InterestExpense"],
        )

        self.assertEqual(resolution.status, "resolved")
        self.assertEqual(resolution.accepted_concept, "InterestExpense")
        self.assertEqual(resolution.selected_fact.value, 338.0)
        self.assertEqual(resolution.decision_basis, "configured_concept_match")

    def test_interest_expense_nonoperating_is_safe_alternate(self):
        inventory = self._inventory({"InterestExpenseNonoperating": 350000000})

        resolution = self.resolver.resolve(
            "interest_expense",
            inventory,
            ["InterestExpense"],
        )

        self.assertEqual(resolution.status, "resolved")
        self.assertEqual(resolution.accepted_concept, "InterestExpenseNonoperating")
        self.assertEqual(resolution.selected_fact.value, 350.0)
        self.assertEqual(
            resolution.decision_basis,
            "safe_interest_expense_alternate",
        )

    def test_interest_paid_is_rejected_as_cash_flow_proxy(self):
        inventory = self._inventory({"InterestPaidNet": 350000000})

        resolution = self.resolver.resolve(
            "interest_expense",
            inventory,
            ["InterestExpense"],
        )

        self.assertEqual(resolution.status, "unresolved")
        self.assertIsNone(resolution.selected_fact)
        self.assertEqual(
            resolution.rejected_candidates[0].classification,
            "cash_flow_proxy",
        )

    def test_lease_interest_is_rejected_as_narrower_component(self):
        inventory = self._inventory({"FinanceLeaseInterestExpense": 12000000})

        resolution = self.resolver.resolve(
            "interest_expense",
            inventory,
            ["InterestExpense"],
        )

        self.assertEqual(resolution.status, "unresolved")
        self.assertEqual(
            resolution.rejected_candidates[0].classification,
            "narrower_component",
        )


if __name__ == "__main__":
    unittest.main()
