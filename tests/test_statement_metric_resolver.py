"""Tests for resolving metrics from extracted statement rows."""

import unittest

from credit_research_agent.statement_extractor import StatementLineItem
from credit_research_agent.statement_metric_resolver import StatementMetricResolver


def _row(label, value, statement_type="cash_flow_statement", concept=None):
    return StatementLineItem(
        company="Example Co",
        ticker="EX",
        fiscal_year=2025,
        statement_type=statement_type,
        row_label=label,
        normalized_label=" ".join(
            "".join(ch.lower() if ch.isalnum() else " " for ch in label).split()
        ),
        value=value,
        unit="USD millions",
        period_end="Jan 31, 2025",
        column_label="Jan 31, 2025",
        xbrl_concept=concept,
        source_url="https://www.sec.gov/example.htm",
        accession_number="0000000000-26-000001",
        confidence="high" if concept else "medium",
    )


class StatementMetricResolverTest(unittest.TestCase):
    """Test metric semantics over statement rows."""

    def setUp(self):
        self.resolver = StatementMetricResolver()

    def test_accepts_cash_capex_row(self):
        resolution = self.resolver.resolve(
            "capital_expenditures",
            2025,
            [_row("Purchases of property and equipment", -250.0)],
        )

        self.assertEqual(resolution.status, "verified_statement")
        self.assertEqual(resolution.metric_value.value, -250.0)
        self.assertEqual(resolution.decision_basis, "verified_statement_cash_capex")

    def test_rejects_ppe_balance_as_capex(self):
        resolution = self.resolver.resolve(
            "capital_expenditures",
            2025,
            [_row("Property and equipment, net", 1000.0, "balance_sheet")],
        )

        self.assertEqual(resolution.status, "statement_row_not_found")

    def test_rejects_capex_incurred_not_yet_paid(self):
        resolution = self.resolver.resolve(
            "capital_expenditures",
            2025,
            [_row("Capital expenditures incurred but not yet paid", 40.0)],
        )

        self.assertEqual(resolution.status, "statement_row_not_found")
        self.assertIn("not cash capex", resolution.rejected_items[0]["reason"])

    def test_accepts_statement_confirmed_interest_expense_debt(self):
        resolution = self.resolver.resolve(
            "interest_expense",
            2025,
            [
                _row(
                    "Interest expense",
                    120.0,
                    "income_statement",
                    "InterestExpenseDebt",
                )
            ],
        )

        self.assertEqual(resolution.status, "verified_statement")
        self.assertEqual(resolution.metric_value.xbrl_concept, "statement:InterestExpenseDebt")

    def test_accepts_dividends_paid_not_per_share(self):
        resolution = self.resolver.resolve(
            "dividend_payments",
            2025,
            [_row("Dividends paid", -50.0)],
        )

        self.assertEqual(resolution.status, "verified_statement")
        self.assertEqual(resolution.metric_value.value, -50.0)

    def test_long_term_debt_rejects_due_within_one_year_row(self):
        row = _row(
            "Long-term debt due within one year",
            2500.0,
            "balance_sheet",
            "LongTermDebtCurrent",
        )

        long_term = self.resolver.resolve("long_term_debt", 2025, [row])
        current = self.resolver.resolve("current_debt", 2025, [row])

        self.assertEqual(long_term.status, "statement_row_not_found")
        self.assertEqual(current.status, "verified_statement")
        self.assertEqual(current.metric_value.value, 2500.0)

    def test_current_debt_aggregates_current_borrowing_components(self):
        resolution = self.resolver.resolve(
            "current_debt",
            2025,
            [
                _row("Loans and notes payable", 1551.0, "balance_sheet", "NotesAndLoansPayable"),
                _row(
                    "Current maturities of long-term debt",
                    1822.0,
                    "balance_sheet",
                    "LongTermDebtCurrent",
                ),
            ],
        )

        self.assertEqual(resolution.status, "verified_statement")
        self.assertEqual(resolution.metric_value.value, 3373.0)
        self.assertEqual(
            resolution.decision_basis,
            "verified_statement_current_debt_aggregated_components",
        )
        self.assertIn("Loans and notes payable + Current maturities", resolution.source_item.row_label)


if __name__ == "__main__":
    unittest.main()
