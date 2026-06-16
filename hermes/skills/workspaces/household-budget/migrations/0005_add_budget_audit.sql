-- 0005: budget_audit — append-only change history for the ledger (Personal is git-less).
--
-- Mirrors people.person_audit / projects.project_audit. Written by every hb mutation
-- (add/transfer/confirm/ignore/upsert/rename/merge/import). No FK: the log must survive
-- entity delete/rename/merge. Read with `hb audit [--entity <id>] [--limit N]`.
-- Folded into schema.sql at user_version = 5; this migration upgrades existing v4 DBs.
CREATE TABLE budget_audit (
  seq       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        TEXT NOT NULL,
  action    TEXT NOT NULL,
  tbl       TEXT,
  entity    TEXT,
  field     TEXT,
  old_value TEXT,
  new_value TEXT,
  note      TEXT
);
CREATE INDEX ix_budget_audit_entity ON budget_audit(entity);
