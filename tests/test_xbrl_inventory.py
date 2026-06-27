"""Tests for annual XBRL fact inventory building."""

import unittest

from credit_research_agent.xbrl_inventory import XBRLFactInventoryBuilder


class XBRLFactInventoryTest(unittest.TestCase):
    """Test SEC companyfacts inventory construction."""

    def test_builds_best_annual_facts_and_normalizes_values(self):
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "InterestExpense": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2024,
                                    "fp": "Q1",
                                    "form": "10-Q",
                                    "filed": "2024-05-01",
                                    "end": "2024-03-31",
                                    "val": 10000000,
                                },
                                {
                                    "fy": 2024,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2025-02-01",
                                    "end": "2024-12-31",
                                    "val": 350000000,
                                },
                            ]
                        }
                    },
                    "InterestPaidNet": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2024,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2025-02-01",
                                    "end": "2024-12-31",
                                    "val": 0,
                                }
                            ]
                        }
                    },
                }
            }
        }

        inventory = XBRLFactInventoryBuilder().build(companyfacts, 2024)

        interest = inventory.by_concept["InterestExpense"]
        self.assertEqual(interest.value, 350.0)
        self.assertEqual(interest.raw_value, 350000000)
        self.assertEqual(interest.form, "10-K")
        self.assertFalse(interest.is_zero)

        paid = inventory.by_concept["InterestPaidNet"]
        self.assertEqual(paid.value, 0.0)
        self.assertTrue(paid.is_zero)

    def test_search_concepts_returns_related_facts(self):
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "InterestExpenseNonoperating": {
                        "units": {
                            "USD": [
                                {
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2026-02-01",
                                    "end": "2025-12-31",
                                    "val": 338000000,
                                }
                            ]
                        }
                    }
                }
            }
        }

        inventory = XBRLFactInventoryBuilder().build(companyfacts, 2025)
        matches = inventory.search_concepts(["interest"])

        self.assertEqual([fact.concept for fact in matches], ["InterestExpenseNonoperating"])


if __name__ == "__main__":
    unittest.main()
