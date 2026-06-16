-- HouseholdBudget — SQLite schema v2 (engine: hb). stdlib sqlite3 only.
--
-- An analytical, multi-currency household ledger. Designed so spending/expense can be
-- sliced by ANY axis (time, store, item, category, currency, payment account, scope,
-- project, counterparty, …) and extended with new axes without a redesign.
--
-- Shape:
--   * facts     : transactions (expense|income) + line_items + claims;
--                 transfers (two-sided: account A -> account B, with fee/fx)
--   * masters   : currencies, categories(hierarchical), stores, items,
--                 payment_accounts, projects (=== ~/Workspaces/Projects/**),
--                 counterparties (typed: project|person|company)
--   * extensible: tag_axes + transaction_tags  (free axes: country, income_source, …)
--
-- Principles:
--   * Money is exact decimal TEXT (no float). Reporting currency = JPY.
--   * Stable, state-free ids: review_status carries state, never the id.
--   * Raw + normalized kept; unmatched -> sentinels + needs_review (never blocks intake).
--   * Privacy invariant: original documents are never stored (source_document_saved = 0).
--   * Schema is versioned (user_version); evolve via migrations/, never destructive rebuild.

PRAGMA foreign_keys = ON;

-- ============================ config ============================
CREATE TABLE currencies (
  code     TEXT PRIMARY KEY,
  label    TEXT NOT NULL,
  decimals INTEGER NOT NULL CHECK (decimals >= 0)
);

CREATE TABLE categories (
  id            TEXT PRIMARY KEY,
  label         TEXT NOT NULL,
  parent_id     TEXT REFERENCES categories(id),
  review_status TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored'))
);

-- ============================ masters ============================
CREATE TABLE stores (
  id                  TEXT PRIMARY KEY,
  canonical_name      TEXT NOT NULL,
  default_category_id TEXT NOT NULL REFERENCES categories(id),
  review_status       TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  last_seen_at        TEXT
);

CREATE TABLE items (
  id                  TEXT PRIMARY KEY,
  canonical_name      TEXT NOT NULL,
  default_category_id TEXT NOT NULL REFERENCES categories(id),
  review_status       TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  last_seen_at        TEXT
);

CREATE TABLE payment_accounts (
  id               TEXT PRIMARY KEY,
  label            TEXT NOT NULL,
  type             TEXT NOT NULL CHECK (type IN
                     ('bank_account','cash','credit_card','crypto_wallet','e_wallet',
                      'multi_currency_account','multi_currency_card','unknown')),
  default_currency TEXT NOT NULL REFERENCES currencies(code),
  display_hint     TEXT,
  review_status    TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored'))
);

-- Who settles / reimburses an expense. Typed so "bill a project" vs "bill a person"
-- vs "bill a company" are all first-class.
CREATE TABLE counterparties (
  id             TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  type           TEXT NOT NULL CHECK (type IN ('project','person','company','unknown')),
  default_scope  TEXT NOT NULL CHECK (default_scope IN
                   ('business_expense','reimbursable','shared','excluded')),
  review_status  TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored'))
);

-- A unit of work. id/slug aligns 1:1 with a directory under ~/Workspaces/Projects/**.
-- Spending dimension ("which project") + a default counterparty (overridable per claim).
CREATE TABLE projects (
  id                      TEXT PRIMARY KEY,           -- slug == Projects/<id>
  canonical_name          TEXT NOT NULL,
  dir_path                TEXT,                        -- e.g. ~/Workspaces/Projects/<id>
  default_counterparty_id TEXT REFERENCES counterparties(id),
  default_scope           TEXT NOT NULL DEFAULT 'business_expense' CHECK (default_scope IN
                            ('household','business_expense','reimbursable','shared','excluded')),
  review_status           TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  last_seen_at            TEXT
);

CREATE TABLE subscriptions (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  store_id          TEXT REFERENCES stores(id),
  item_id           TEXT REFERENCES items(id),
  budget_scope      TEXT NOT NULL CHECK (budget_scope IN
                      ('household','business_expense','reimbursable','shared','excluded')),
  project_id        TEXT REFERENCES projects(id),
  counterparty_id   TEXT REFERENCES counterparties(id),
  billing_cycle     TEXT NOT NULL CHECK (billing_cycle IN ('weekly','monthly','yearly','unknown')),
  expected_value    TEXT,
  expected_currency TEXT REFERENCES currencies(code),
  review_status     TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  note              TEXT
);

-- ============================ relations ============================
-- All searchable names (canonical + aliases) per entity type, normalized.
CREATE TABLE entity_aliases (
  entity_type TEXT NOT NULL CHECK (entity_type IN
                ('store','item','category','payment_account','counterparty','project')),
  entity_id   TEXT NOT NULL,
  alias       TEXT NOT NULL,
  alias_norm  TEXT NOT NULL,
  is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  PRIMARY KEY (entity_type, alias_norm)
);
CREATE INDEX ix_alias_entity ON entity_aliases(entity_type, entity_id);

CREATE TABLE payment_account_currencies (
  payment_account_id TEXT NOT NULL REFERENCES payment_accounts(id),
  currency           TEXT NOT NULL REFERENCES currencies(code),
  PRIMARY KEY (payment_account_id, currency)
);

CREATE TABLE store_payment_options (
  store_id           TEXT NOT NULL REFERENCES stores(id),
  payment_account_id TEXT NOT NULL REFERENCES payment_accounts(id),
  currency           TEXT NOT NULL REFERENCES currencies(code),
  is_default         INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
  PRIMARY KEY (store_id, payment_account_id, currency)
);
CREATE UNIQUE INDEX ux_store_default_payment ON store_payment_options(store_id) WHERE is_default = 1;

-- ============================ facts: transactions ============================
-- type is expense|income only; money MOVED between own accounts lives in `transfers`.
CREATE TABLE transactions (
  id                    TEXT PRIMARY KEY,
  date                  TEXT NOT NULL,
  month                 TEXT GENERATED ALWAYS AS (substr(date, 1, 7)) STORED,
  type                  TEXT NOT NULL DEFAULT 'expense' CHECK (type IN ('expense','income')),
  amount_value          TEXT NOT NULL,
  amount_currency       TEXT NOT NULL REFERENCES currencies(code),
  reporting_value       TEXT NOT NULL,
  reporting_currency    TEXT NOT NULL DEFAULT 'JPY' CHECK (reporting_currency = 'JPY'),
  fx_rate               TEXT NOT NULL,
  fx_date               TEXT NOT NULL,
  fx_source             TEXT NOT NULL CHECK (fx_source IN
                          ('manual','receipt','card_statement','exchange_api','estimated','not_required')),
  store_raw_name        TEXT,
  store_id              TEXT REFERENCES stores(id),
  store_confidence      REAL,
  payment_account_id    TEXT NOT NULL REFERENCES payment_accounts(id),
  payment_raw_text      TEXT,
  payment_confidence    REAL,
  category_id           TEXT NOT NULL REFERENCES categories(id),
  budget_scope          TEXT NOT NULL DEFAULT 'household' CHECK (budget_scope IN
                          ('household','business_expense','reimbursable','shared','excluded')),
  project_id            TEXT REFERENCES projects(id),
  status                TEXT NOT NULL CHECK (status IN ('needs_review','confirmed','ignored')),
  confidence            REAL DEFAULT 1,
  source_kind           TEXT,
  source_document_saved INTEGER NOT NULL DEFAULT 0 CHECK (source_document_saved = 0),
  source_raw_text_saved INTEGER NOT NULL DEFAULT 0 CHECK (source_raw_text_saved IN (0,1)),
  source_summary        TEXT,
  source_organization   TEXT,
  source_external_ref   TEXT,   -- non-sensitive references as JSON text (invoice/order no.)
  note                  TEXT,
  subscription_id       TEXT REFERENCES subscriptions(id),
  created_at            TEXT NOT NULL,
  updated_at            TEXT NOT NULL
);
CREATE INDEX ix_txn_month        ON transactions(month);
CREATE INDEX ix_txn_store        ON transactions(store_id);
CREATE INDEX ix_txn_category     ON transactions(category_id);
CREATE INDEX ix_txn_scope_status ON transactions(budget_scope, status);
CREATE INDEX ix_txn_project      ON transactions(project_id);
CREATE INDEX ix_txn_subscription ON transactions(subscription_id);

CREATE TABLE transaction_line_items (
  txn_id          TEXT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  seq             INTEGER NOT NULL,
  raw_name        TEXT NOT NULL,
  item_id         TEXT REFERENCES items(id),
  amount_value    TEXT NOT NULL,
  amount_currency TEXT NOT NULL REFERENCES currencies(code),
  category_id     TEXT NOT NULL REFERENCES categories(id),
  confidence      REAL,
  PRIMARY KEY (txn_id, seq)
);
CREATE INDEX ix_li_item ON transaction_line_items(item_id);

CREATE TABLE claims (
  txn_id                      TEXT PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
  counterparty_id             TEXT NOT NULL REFERENCES counterparties(id),
  status                      TEXT NOT NULL CHECK (status IN
                                ('not_submitted','submitted','approved','partially_reimbursed',
                                 'reimbursed','rejected','not_applicable')),
  expected_value              TEXT,
  expected_currency           TEXT REFERENCES currencies(code),
  submitted_at                TEXT,
  reimbursed_at               TEXT,
  linked_original_txn_id      TEXT REFERENCES transactions(id),
  linked_reimbursement_txn_id TEXT REFERENCES transactions(id),
  note                        TEXT
);
CREATE INDEX ix_claims_party  ON claims(counterparty_id);
CREATE INDEX ix_claims_status ON claims(status);

-- ============================ facts: transfers (two-sided) ============================
-- Money moved between OWN accounts (incl. currency exchange). Excluded from
-- spend/income aggregation by living in its own table.
CREATE TABLE transfers (
  id                    TEXT PRIMARY KEY,
  date                  TEXT NOT NULL,
  month                 TEXT GENERATED ALWAYS AS (substr(date, 1, 7)) STORED,
  from_account_id       TEXT NOT NULL REFERENCES payment_accounts(id),
  from_value            TEXT NOT NULL,
  from_currency         TEXT NOT NULL REFERENCES currencies(code),
  to_account_id         TEXT NOT NULL REFERENCES payment_accounts(id),
  to_value              TEXT NOT NULL,
  to_currency           TEXT NOT NULL REFERENCES currencies(code),
  fee_value             TEXT,
  fee_currency          TEXT REFERENCES currencies(code),
  fee_account_id        TEXT REFERENCES payment_accounts(id),
  fx_rate               TEXT,                 -- recorded rate from_currency -> to_currency
  reporting_value       TEXT,                 -- JPY equivalent of the moved amount (reference)
  status                TEXT NOT NULL CHECK (status IN ('needs_review','confirmed','ignored')),
  confidence            REAL DEFAULT 1,
  source_kind           TEXT,
  source_document_saved INTEGER NOT NULL DEFAULT 0 CHECK (source_document_saved = 0),
  source_raw_text_saved INTEGER NOT NULL DEFAULT 0 CHECK (source_raw_text_saved IN (0,1)),
  source_summary        TEXT,
  note                  TEXT,
  created_at            TEXT NOT NULL,
  updated_at            TEXT NOT NULL
);
CREATE INDEX ix_transfer_month ON transfers(month);
CREATE INDEX ix_transfer_from  ON transfers(from_account_id);
CREATE INDEX ix_transfer_to    ON transfers(to_account_id);

-- ============================ extensibility: flexible tags ============================
-- Registry of long-tail axes (country, income_source, …). New axis = one row here.
CREATE TABLE tag_axes (
  axis          TEXT PRIMARY KEY,
  label         TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'confirmed' CHECK (review_status IN ('needs_review','confirmed','ignored'))
);

CREATE TABLE transaction_tags (
  txn_id     TEXT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  axis       TEXT NOT NULL REFERENCES tag_axes(axis),
  value      TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  PRIMARY KEY (txn_id, axis, value_norm)
);
CREATE INDEX ix_txn_tags_axis ON transaction_tags(axis, value_norm);

-- ============================ triggers: currency compatibility ============================
-- txn.amount_currency must be allowed by the chosen payment account.
CREATE TRIGGER trg_txn_currency_ins
BEFORE INSERT ON transactions FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM payment_account_currencies
                 WHERE payment_account_id = NEW.payment_account_id AND currency = NEW.amount_currency)
BEGIN
  SELECT RAISE(ABORT, 'amount.currency not allowed by payment_account');
END;

CREATE TRIGGER trg_txn_currency_upd
BEFORE UPDATE OF amount_currency, payment_account_id ON transactions FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM payment_account_currencies
                 WHERE payment_account_id = NEW.payment_account_id AND currency = NEW.amount_currency)
BEGIN
  SELECT RAISE(ABORT, 'amount.currency not allowed by payment_account');
END;

-- transfer legs must be allowed by their respective accounts.
CREATE TRIGGER trg_transfer_from_currency_ins
BEFORE INSERT ON transfers FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM payment_account_currencies
                 WHERE payment_account_id = NEW.from_account_id AND currency = NEW.from_currency)
BEGIN
  SELECT RAISE(ABORT, 'transfer.from_currency not allowed by from_account');
END;

CREATE TRIGGER trg_transfer_to_currency_ins
BEFORE INSERT ON transfers FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM payment_account_currencies
                 WHERE payment_account_id = NEW.to_account_id AND currency = NEW.to_currency)
BEGIN
  SELECT RAISE(ABORT, 'transfer.to_currency not allowed by to_account');
END;

-- store payment option currency must be allowed by that payment account.
CREATE TRIGGER trg_store_payopt_currency_ins
BEFORE INSERT ON store_payment_options FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM payment_account_currencies
                 WHERE payment_account_id = NEW.payment_account_id AND currency = NEW.currency)
BEGIN
  SELECT RAISE(ABORT, 'store payment option currency not allowed by payment_account');
END;

-- ============================ reporting views ============================
-- reporting_value is always JPY (0 decimals) -> safe to SUM as INTEGER in SQL.
CREATE VIEW v_monthly_category AS
  SELECT month, category_id, COUNT(*) AS n, SUM(CAST(reporting_value AS INTEGER)) AS total_jpy
  FROM transactions GROUP BY month, category_id;

CREATE VIEW v_monthly_scope AS
  SELECT month, budget_scope, COUNT(*) AS n, SUM(CAST(reporting_value AS INTEGER)) AS total_jpy
  FROM transactions GROUP BY month, budget_scope;

CREATE VIEW v_monthly_project AS
  SELECT month, project_id, COUNT(*) AS n, SUM(CAST(reporting_value AS INTEGER)) AS total_jpy
  FROM transactions WHERE project_id IS NOT NULL GROUP BY month, project_id;

CREATE VIEW v_open_reimbursements AS
  SELECT t.id, t.date, t.month, t.project_id, c.counterparty_id, c.status,
         t.amount_value, t.amount_currency, CAST(t.reporting_value AS INTEGER) AS reporting_jpy
  FROM transactions t JOIN claims c ON c.txn_id = t.id
  WHERE t.budget_scope = 'reimbursable'
    AND c.status NOT IN ('reimbursed','rejected','not_applicable');

PRAGMA user_version = 2;
