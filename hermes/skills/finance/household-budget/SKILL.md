---
name: household-budget
description: >-
  Manage the household budget ledger (SQLite DB v2) — record receipts/invoices as
  normalized transactions or two-sided transfers, validate, and report by any axis
  (month, category, store, item, currency, account, scope, project, counterparty, tag).
  Use when the user shares a receipt/expense or asks about spending, 家計簿, レシート,
  経費, 立替, サブスク, 振替, expenses, reimbursement, subscriptions, budget.
version: 0.2.0
author: Hermes Agent
metadata:
  hermes:
    tags: [household-budget, finance, sqlite, expenses, reimbursement, subscriptions, multi-currency]
    category: finance
---

# Household budget

An analytical, multi-currency SQLite ledger. The DB is the source of truth at
`~/Workspaces/Personal/HouseholdBudget/data/budget.db`; JSON/CSV under `data/export/`
is a regenerable mirror. Data is **sensitive** (financial) — handle per `Personal/AGENTS.md`.
The full model is `references/data-model.md` (the canon); `schema.sql` is the structure.

## When to use
- The user shares a receipt, invoice, card-statement line, or a transfer/exchange to record.
- The user asks about spending, a monthly summary, open reimbursements, subscriptions, or a
  custom breakdown ("by store / by project / by currency …").

## Engine (run via the bundled CLI)
All operations go through `${HERMES_SKILL_DIR}/scripts/hb` (Python stdlib, no deps);
defaults to `--root ~/Workspaces/Personal/HouseholdBudget`. Pass `--help` to any subcommand.

```
# intake
hb add --input drafts/x.json [--dry-run]        # normalize + append a transaction
hb transfer --input drafts/x.json [--dry-run]   # two-sided transfer / currency exchange
# review & maintain masters
hb review                                        # list pending (needs_review)
hb confirm|ignore --kind <k> --id <id>           # flip review state (id never changes)
hb upsert-entity --kind store|item|payment_account|counterparty|project --name "..."
hb rename-entity --kind <k> --old <id> --new <id>     # FK-safe
hb merge-entity  --kind <k> --old <id> --into <id>    # FK-safe dedupe
# report (the analytical core)
hb summary --month YYYY-MM
hb report --by <axis> [--month|--from|--to] [--type] [--scope] [--where axis=value]
hb subscriptions ; hb reimbursements [--month YYYY-MM]
# data ops
hb validate ; hb export --format both ; hb backup [--keep N]
hb init [--force] ; hb import-json [--src DIR] ; hb migrate
```
`report --by`: `month|type|scope|category|store|item|account|currency|project|counterparty|tag:<axis>`.

## Recording a receipt (workflow)
1. Extract date, total, store, payment, and line items from the source.
2. Write a normalized draft JSON to `drafts/` (shape: `references/data-model.md` §6;
   `references/examples/*.json` are synthetic shape references).
3. Dry-run: `hb add --input drafts/draft.json --dry-run`; inspect the normalized result.
4. Append: `hb add --input drafts/draft.json` (runs `validate` afterward).
5. `source.document_saved` is forced false — never persist original images/PDFs/OCR text.
6. When unsure, use sentinels (`store_unknown`/`item_unknown`/`pay_unknown`/`cp_unknown`/
   `uncategorized`) + `status: needs_review` rather than guessing; create pending masters
   with `hb upsert-entity` (stable ids; state lives in `review_status`).

## Rules
- Money is decimal strings; reporting currency is JPY (non-JPY needs `reporting_amount`
  with `fx_rate`/`fx_date`/`fx_source`).
- Money moved between own accounts is a **transfer** (`hb transfer`), not a transaction —
  it is excluded from spend/income aggregation.
- Summarize results to chat; never paste raw balances/account numbers. No external sends
  without an explicit OK.
- Don't hand-edit `budget.db` or the mirror — use `hb`. Schema evolves via `migrations/`
  (`hb migrate`), never `init --force` on a live DB.
