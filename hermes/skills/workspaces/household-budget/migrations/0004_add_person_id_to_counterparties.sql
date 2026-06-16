-- 0004: link person-type counterparties to the People registry.
--
-- counterparties.person_id holds the People person_id (== persons.id in
-- ~/Workspaces/Personal/People/data/people.db) for `type = 'person'` rows. People is a
-- separate DB, so this is a soft reference (no enforced FK) — exactly like
-- projects.dir_path points at ~/Workspaces/Projects/<slug>. `hb validate` cross-checks
-- that every person counterparty's person_id resolves against the People export.
ALTER TABLE counterparties ADD COLUMN person_id TEXT;
