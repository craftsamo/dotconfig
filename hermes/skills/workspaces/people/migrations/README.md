# migrations/

Incremental schema changes for the People DB. The baseline schema (`../schema.sql`)
creates a database at `user_version = 1`. Each migration advances the database to the next
version.

## Convention
- Filename: `NNNN_short_description.{sql,py}` where `NNNN` is the **target** `user_version`
  (zero-padded, strictly increasing). The first migration is `0002_*`.
- `.sql` migration: plain SQL applied in one transaction; the runner then sets
  `PRAGMA user_version = NNNN`.
- `.py` migration: defines `def up(con)` (receives a `sqlite3.Connection`). Use for data
  transforms / collision handling that SQL alone cannot express.
- A migration must leave the DB consistent at COMMIT (`PRAGMA foreign_key_check` clean).
  Prefer `PRAGMA defer_foreign_keys = ON` for multi-table id rewrites.

## Apply
```
pp migrate            # apply all pending (version > current), in order
pp migrate --dry-run  # show what would run, change nothing
```

Never run `pp init --force` on a live DB to "upgrade" — it destroys data. Evolve forward
with migrations; the baseline schema is only for creating a fresh DB.

## legacy/
`legacy/migrate_people.py` is the one-time importer that built `people.db` (v1) from the
old flat per-person JSON registry (`data/<id>.json`). Kept for provenance; not part of the
`pp migrate` sequence.
