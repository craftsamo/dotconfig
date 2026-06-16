# HouseholdBudget — data model (canon)

Single source of truth for the ledger's structure. The engine (`scripts/hb`) and the
schema (`schema.sql`) conform to this document. The SQLite DB at
`~/Workspaces/Personal/HouseholdBudget/data/budget.db` is authoritative; JSON/CSV under
`data/export/` is a regenerable mirror (never hand-edited).

## 1. Principles
- **Analytical ledger.** Every transaction carries many axes so spend/income can be
  summed by any of them: time, store, item, category, currency, payment account,
  budget scope, project, counterparty, subscription, and free **tags**.
- **Exact money.** Amounts are decimal **strings** (`"1280"`, `"38.50"`), never floats.
  Reporting currency is **JPY**.
- **Stable, state-free ids.** An id never encodes state. "pending"/"unknown" live in
  `review_status` (or `status`), not in the id. Ids are lowercase slugs.
- **Robust intake.** Extraction from heterogeneous receipts is lossy. Unmatched fields
  fall back to **sentinels** + `status = needs_review` and never block recording. The
  raw text is kept next to the normalized value.
- **Privacy invariant.** Original documents/images are never stored
  (`source_document_saved` is constrained to `0`). Never store card numbers/last-4/CVV,
  PINs, wallet keys/seed phrases, or full wallet addresses. Use `payment_account_id`
  (+ optional non-sensitive `display_hint`).
- **Versioned.** Schema evolves via `migrations/` (`hb migrate`), never a destructive
  rebuild.

## 2. Identity & state
| entity            | id form                         | sentinel        |
|-------------------|---------------------------------|-----------------|
| category          | bare slug (`food`, `food_lunch`)| `uncategorized` |
| store             | `store_<slug>`                  | `store_unknown` |
| item              | `item_<slug>`                   | `item_unknown`  |
| payment_account   | `pay_<slug>`                    | `pay_unknown`   |
| project           | `proj_<slug>` (slug == `~/Workspaces/Projects/<slug>`) | — |
| counterparty      | `cp_<slug>`                     | `cp_unknown`    |
| subscription      | `sub_<slug>`                    | —               |
| transaction       | `txn_<YYYYMMDD>_<store-slug>[_n]`| —              |
| transfer          | `xfer_<YYYYMMDD>_<from>_<to>[_n]`| —              |

`review_status ∈ {needs_review, confirmed, ignored}` on every master. Facts
(transactions, transfers) use `status` with the same three values. Sentinels always
exist and are `confirmed`.

## 3. Money, currency, FX
- `amount = {value, currency}` keeps the receipt's own currency.
- Reporting is JPY. If `amount.currency == JPY`, the engine fills
  `reporting_amount = {value: amount.value, currency: JPY, fx_rate:"1", fx_date: date,
  fx_source:"not_required"}`.
- For non-JPY, `reporting_amount` is **required**: `{value, currency:"JPY", fx_rate,
  fx_date, fx_source}` where `fx_source ∈
  {manual, receipt, card_statement, exchange_api, estimated, not_required}`.
- A payment account declares its allowed `currencies`; a transaction's
  `amount.currency` must be one of them (enforced by trigger).

## 4. Masters
- **currencies** `{code, label, decimals}` — e.g. JPY/0, USD/2, MYR/2, USDC/6.
- **categories** `{id, label, parent_id?, review_status}` — hierarchical (e.g.
  `food_lunch → food`). `uncategorized` is the sentinel.
- **stores** `{id, canonical_name, default_category_id, review_status, last_seen_at}`
  plus alias list and `payment_options[]` (preferred account+currency, one default).
- **items** `{id, canonical_name, default_category_id, review_status, last_seen_at}`
  plus aliases.
- **payment_accounts** `{id, label, type, currencies[], default_currency,
  display_hint?, review_status}`; `type ∈ {bank_account, cash, credit_card,
  crypto_wallet, e_wallet, multi_currency_account, multi_currency_card, unknown}`.
- **projects** `{id, canonical_name, dir_path?, default_counterparty_id?,
  default_scope, review_status, last_seen_at}` — 1:1 with `~/Workspaces/Projects/<slug>`.
  Used as a spend dimension and to default a claim's counterparty.
- **counterparties** `{id, canonical_name, type, default_scope, review_status, person_id?}` —
  who settles/reimburses; `type ∈ {project, person, company, unknown}`. For `type = 'person'`,
  `person_id` is a soft reference to the People registry (`~/Workspaces/Personal/People`,
  like `projects.dir_path`). Added by migration `0004`. `hb validate` cross-checks it by
  **calling the People CLI** (`pp list --json`, read-only — never opening `people.db`; see
  `skills/workspaces/_cross.py`), and `pp validate` checks the same edge from the People side.
- **subscriptions** `{id, name, store_id?, item_id?, budget_scope, project_id?,
  counterparty_id?, billing_cycle, expected_amount?, review_status, note?}`;
  `billing_cycle ∈ {weekly, monthly, yearly, unknown}`.

All masters share **aliases** (canonical + variants, normalized) used to map raw
receipt text → the entity. Normalization = NFKC + casefold + collapse spaces.

## 5. Facts
- **transactions** — one expense/income event. `type ∈ {expense, income}` (money
  moved between own accounts is a **transfer**, not a transaction). Carries:
  amount(+reporting), store(raw+id+confidence), payment(account+raw+confidence),
  `category_id`, `budget_scope`, `project_id?`, `status`, `confidence`, source block,
  `note?`, `subscription_id?`.
- **transaction_line_items** — `{seq, raw_name, item_id?, amount, category_id,
  confidence?}`. Enables by-item and accurate by-category even on mixed receipts.
- **claims** — attached to a transaction when `budget_scope ∈
  {business_expense, reimbursable, shared}`. `{counterparty_id, status,
  expected_reimbursement_amount?, submitted_at?, reimbursed_at?,
  linked_original_transaction_id?, linked_reimbursement_transaction_id?, note?}`;
  `status ∈ {not_submitted, submitted, approved, partially_reimbursed, reimbursed,
  rejected, not_applicable}`.
- **transfers** — two-sided money movement (incl. currency exchange). `{date, from:
  {account, amount}, to: {account, amount}, fee?, fx_rate?, reporting_amount?, status,
  source, note?}`. Excluded from spend/income aggregation by construction.
- **tags** — `transaction_tags(axis, value)` for long-tail axes. Axes are registered
  in `tag_axes` (e.g. `country`, `income_source`); values are free text (normalized).

`budget_scope ∈ {household, business_expense, reimbursable, shared, excluded}`.
`household` is the default when there is no evidence otherwise.

## 6. Draft shapes (input to the engine)
Intake adapters (manual, Telegram extraction, future API/cron) all emit a **draft**
that the engine normalizes + appends. Only `date` and `amount` are strictly required;
the engine fills defaults, matches masters by alias, applies sentinels, and sets
`status = needs_review` when anything is uncertain.

### Transaction draft
```json
{
  "date": "2026-06-06",
  "type": "expense",
  "amount": { "value": "120.80", "currency": "MYR" },
  "reporting_amount": {
    "value": "4016", "currency": "JPY",
    "fx_rate": "33.24", "fx_date": "2026-06-06", "fx_source": "estimated"
  },
  "store":   { "raw_name": "Sample Mart", "store_id": null, "confidence": 0.9 },
  "payment": { "payment_account_id": "pay_unknown", "raw_text": "Cash", "confidence": 0.5 },
  "category_id": "food",
  "budget_scope": "household",
  "project_id": null,
  "line_items": [
    { "raw_name": "Milk 1L", "item_id": null, "category_id": "food",
      "amount": { "value": "9.50", "currency": "MYR" } }
  ],
  "claim": null,
  "tags": [ { "axis": "country", "value": "Malaysia" } ],
  "source": {
    "kind": "receipt_image", "document_saved": false, "raw_text_saved": false,
    "summary": null, "organization": null,
    "external_reference": { "invoice_number": "INV-0001" }
  },
  "note": null,
  "subscription_id": null
}
```
- `claim` is auto-created when `budget_scope` is business/reimbursable/shared, or when a
  counterparty alias matches `note`/`summary`/`organization`. `expected_reimbursement_amount`
  defaults to `amount`.
- `source.external_reference` is stored verbatim as JSON in `source_external_ref`
  (non-sensitive references only: invoice/order numbers).
- `source.document_saved` is forced to `false`.

### Transfer draft
```json
{
  "date": "2026-06-06",
  "from": { "payment_account_id": "pay_wise_jpy", "amount": { "value": "50000", "currency": "JPY" } },
  "to":   { "payment_account_id": "pay_wise_myr", "amount": { "value": "1480", "currency": "MYR" } },
  "fee":  { "value": "300", "currency": "JPY", "payment_account_id": "pay_wise_jpy" },
  "fx_rate": "33.78",
  "reporting_amount": { "value": "50000", "currency": "JPY" },
  "source": { "kind": "manual", "document_saved": false, "raw_text_saved": false },
  "note": null
}
```

## 7. Normalization rules
- Put each default in the **narrowest stable master**: store aliases / payment options
  → store; item aliases / default category → item; recurring → subscription;
  reimbursement parties / default scope → counterparty; project defaults → project.
- On intake the engine: matches `store.raw_name`/`line_items[].raw_name` to masters by
  normalized alias; fills `category_id` from the matched store/item default; selects a
  `payment_account` from the store's payment options (currency-aware); auto-claims on
  scope/counterparty match.
- Low confidence / no match → sentinel id + `status = needs_review`. Prefer creating a
  **pending entity** (`review_status = needs_review`, stable id) over guessing.

## 8. Intake adapter seam
Every source produces the same **draft → `hb add` (or `hb transfer add`)** contract:
- manual / Telegram extraction (agent + vision) — unstructured → LLM.
- future API/cron adapters (FX rates, Wise, billing emails) — structured → plain Python.
The DB/engine are source-agnostic; new adapters only need to emit a valid draft.

## 9. Extensibility
- **New axis** → register in `tag_axes` and start tagging; no schema change.
- **New core field/relation** → a numbered migration under `migrations/` (`hb migrate`).
- The baseline schema is `user_version = 2`.
