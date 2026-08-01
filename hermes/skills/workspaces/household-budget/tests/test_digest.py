import runpy
import sqlite3
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
HB = runpy.run_path(str(SKILL_DIR / "scripts" / "hb"), run_name="hb_digest_test")


class DigestTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript((SKILL_DIR / "schema.sql").read_text(encoding="utf-8"))
        self._seed_masters()
        self._seed_transactions()

    def tearDown(self):
        self.con.close()

    def _seed_masters(self):
        self.con.execute("INSERT INTO currencies VALUES ('JPY', 'Japanese yen', 0)")
        self.con.executemany(
            "INSERT INTO categories VALUES (?, ?, NULL, ?)",
            [("cat_food", "Food", "confirmed"), ("cat_travel", "Travel", "needs_review")],
        )
        self.con.execute(
            "INSERT INTO stores VALUES ('store_shop', 'Example Shop', 'cat_food', 'confirmed', NULL)"
        )
        self.con.execute(
            "INSERT INTO items VALUES ('item_ticket', 'Example Ticket', 'cat_travel', 'needs_review', NULL)"
        )
        self.con.execute(
            "INSERT INTO payment_accounts VALUES "
            "('pay_cash', 'Cash', 'cash', 'JPY', NULL, 'confirmed')"
        )
        self.con.execute("INSERT INTO payment_account_currencies VALUES ('pay_cash', 'JPY')")
        self.con.execute(
            "INSERT INTO counterparties VALUES "
            "('cp_company', 'Example Company', 'company', 'reimbursable', 'confirmed', NULL)"
        )
        self.con.execute(
            "INSERT INTO projects VALUES "
            "('proj_demo', 'Demo Project', NULL, 'cp_company', 'reimbursable', 'confirmed', NULL)"
        )
        self.con.execute(
            "INSERT INTO subscriptions VALUES "
            "('sub_demo', 'Demo Subscription', 'store_shop', NULL, 'household', NULL, NULL, "
            "'monthly', '1000', 'JPY', 'confirmed', NULL)"
        )

    def _add_transaction(self, txn_id, txn_date, value, *, txn_type="expense",
                         category="cat_food", scope="household", status="confirmed",
                         project=None):
        self.con.execute(
            "INSERT INTO transactions "
            "(id, date, type, amount_value, amount_currency, reporting_value, reporting_currency, "
            "fx_rate, fx_date, fx_source, store_id, payment_account_id, category_id, budget_scope, "
            "project_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'JPY', ?, 'JPY', '1', ?, 'not_required', 'store_shop', "
            "'pay_cash', ?, ?, ?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (txn_id, txn_date, txn_type, str(value), str(value), txn_date,
             category, scope, project, status),
        )

    def _add_claim(self, txn_id, status="not_submitted"):
        self.con.execute(
            "INSERT INTO claims (txn_id, counterparty_id, status) VALUES (?, 'cp_company', ?)",
            (txn_id, status),
        )

    def _seed_transactions(self):
        self._add_transaction("txn_june", "2026-06-01", 2000, scope="reimbursable")
        self._add_claim("txn_june")
        self._add_transaction("txn_prior", "2026-07-13", 1000)
        self._add_transaction("txn_current_a", "2026-07-20", 1000)
        self._add_transaction(
            "txn_current_b", "2026-07-25", 500, category="cat_travel",
            scope="reimbursable", status="needs_review", project="proj_demo",
        )
        self._add_claim("txn_current_b", "submitted")
        self._add_transaction("txn_ignored", "2026-07-22", 9000, status="ignored")
        self._add_transaction(
            "txn_income", "2026-07-23", 7000, txn_type="income", status="needs_review"
        )

    def test_weekly_bounds_use_previous_complete_calendar_week(self):
        for day in range(27, 32):
            with self.subTest(day=day):
                bounds = HB["_weekly_bounds"](date(2026, 7, day))
                self.assertEqual(
                    tuple(value.isoformat() for value in bounds),
                    ("2026-07-20", "2026-07-26", "2026-07-13", "2026-07-19"),
                )
        for day in (1, 2):
            with self.subTest(day=day):
                bounds = HB["_weekly_bounds"](date(2026, 8, day))
                self.assertEqual(
                    tuple(value.isoformat() for value in bounds),
                    ("2026-07-20", "2026-07-26", "2026-07-13", "2026-07-19"),
                )

        year_boundary = HB["_weekly_bounds"](date(2026, 1, 1))
        self.assertEqual(
            tuple(value.isoformat() for value in year_boundary),
            ("2025-12-22", "2025-12-28", "2025-12-15", "2025-12-21"),
        )

    def test_previous_month_crosses_year_boundary(self):
        self.assertEqual(HB["_previous_month"]("2026-01"), "2025-12")

    def test_expense_rows_exclude_income_and_ignored(self):
        rows = HB["_expense_rows"](
            self.con, date_from="2026-07-20", date_to="2026-07-26"
        )
        self.assertEqual([row["id"] for row in rows], ["txn_current_a", "txn_current_b"])
        self.assertEqual(HB["_reporting_total"](rows), Decimal("1500"))

    def test_change_label_handles_delta_new_and_missing_history(self):
        self.assertEqual(HB["_change_label"](1500, 1000), "+¥500 · +50%")
        self.assertEqual(HB["_change_label"](500, 0), "+¥500 · new")
        self.assertEqual(HB["_change_label"](500, 0, False), "—")

    def test_weekly_markdown_combines_period_summary_and_actions(self):
        output = HB["_digest_weekly"](
            self.con, {"JPY": 0}, 20, "markdown", today=date(2026, 7, 27)
        )

        self.assertIn("Period: **2026\\-07\\-20–07\\-26**", output)
        self.assertIn("Spending: **¥1,500** · 2\u00a0txns", output)
        self.assertIn("vs prior **\\+¥500 · \\+50%**", output)
        self.assertIn("Income: **¥7,000** · 1\u00a0txn", output)
        self.assertIn("Period review: 2\u00a0txns", output)
        self.assertIn("Open reimbursements: **¥2,500** · 2\u00a0open · oldest 56\u00a0days", output)
        self.assertIn("| Category | Period | Change |", output)
        self.assertIn("| Example Company | ¥2,500 | 2 | 56d |", output)
        self.assertIn("<details><summary>Details</summary>", output)
        self.assertNotIn("¥9,000", output)

    def test_monthly_markdown_compares_expenses_and_adds_analysis(self):
        output = HB["_digest_month_end"](
            self.con, {"JPY": 0}, "2026-07", "markdown"
        )

        self.assertIn("Spending: **¥2,500** · 3\u00a0txns", output)
        self.assertIn("vs prior **\\+¥500 · \\+25%**", output)
        self.assertIn("Period review: 2\u00a0txns", output)
        self.assertIn("Income: **¥7,000** · 1\u00a0txn", output)
        self.assertIn("| Food | ¥2,000 | ±¥0 · 0% |", output)
        self.assertIn("| Travel | ¥500 | \\+¥500 · new |", output)
        self.assertIn("| Household | ¥2,000 | 80% |", output)
        self.assertIn("| Reimbursable | ¥500 | 20% |", output)
        self.assertIn("Demo Project · ¥500", output)
        self.assertIn("Open reimbursements now", output)
        self.assertNotIn("¥9,000", output)

    def test_monthly_markdown_handles_an_empty_ledger(self):
        self.con.execute("DELETE FROM claims")
        self.con.execute("DELETE FROM transactions")

        output = HB["_digest_month_end"](
            self.con, {"JPY": 0}, "2026-07", "markdown"
        )

        self.assertIn("Spending: **¥0** · 0\u00a0txns · vs prior **—**", output)
        self.assertIn("No reportable expenses for this month.", output)
        self.assertNotIn("<details>", output)

    def test_invalid_open_date_does_not_break_weekly_digest(self):
        self._add_transaction(
            "txn_bad_date", "2026-02-30", 100, scope="reimbursable"
        )
        self._add_claim("txn_bad_date")

        output = HB["_digest_weekly"](
            self.con, {"JPY": 0}, 20, "markdown", today=date(2026, 7, 27)
        )

        self.assertIn("3\u00a0open · oldest 56\u00a0days", output)
        self.assertIn("| Example Company | ¥2,600 | 3 | 56d |", output)

    def test_review_backlog_includes_transfers(self):
        self.con.execute(
            "INSERT INTO transfers "
            "(id, date, from_account_id, from_value, from_currency, to_account_id, to_value, "
            "to_currency, status, created_at, updated_at) VALUES "
            "('xfer_review', '2026-07-20', 'pay_cash', '100', 'JPY', 'pay_cash', '100', "
            "'JPY', 'needs_review', '2026-07-20T00:00:00Z', '2026-07-20T00:00:00Z')"
        )

        backlog = dict(HB["_review_backlog"](self.con))
        self.assertEqual(backlog["Transfers"], 1)
        output = HB["_digest_weekly"](
            self.con, {"JPY": 0}, 20, "markdown", today=date(2026, 7, 27)
        )
        self.assertIn("Transfers 1", output)

    def test_all_invalid_open_dates_render_as_unknown(self):
        self.con.execute("DELETE FROM claims")
        self.con.execute("DELETE FROM transactions")
        self._add_transaction(
            "txn_bad_date", "2026-02-30", 100, scope="reimbursable"
        )
        self._add_claim("txn_bad_date")

        weekly = HB["_digest_weekly"](
            self.con, {"JPY": 0}, 20, "markdown", today=date(2026, 7, 27)
        )
        monthly = HB["_digest_month_end"](
            self.con, {"JPY": 0}, "2026-07", "markdown"
        )

        self.assertIn("1\u00a0open · oldest unknown", weekly)
        self.assertIn("| Example Company | ¥100 | 1 | unknown |", weekly)
        self.assertIn("1\u00a0counterparty · oldest unknown", monthly)


if __name__ == "__main__":
    unittest.main()
