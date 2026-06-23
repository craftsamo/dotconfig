---
name: people
description: >-
  Canonical person registry (SQLite v1) — identities, aliases, contacts, languages,
  nationalities, free tags, person<->person relationships, and a regenerable mirror of
  Projects team memberships. Use to resolve a sender/handle to a person, look up who
  someone is, manage the registry, or pull comms context (preferred language, tone,
  roles, permissions). Keyed by person_id; consumed by household-budget
  (counterparties.person_id) and the message-reply skill. 人物, 連絡先, だれ, people, contact.
version: 0.1.0
author: Hermes agent
metadata:
  hermes:
    tags: [people, registry, sqlite, contacts, directory, personal]
    category: workspaces
---

<Goal>

The canonical person registry. The SQLite DB is the source of truth at
`~/Workspaces/Personal/People/data/people.db`; JSON/CSV under `data/export/` is a
regenerable mirror. Data is **sensitive** — handle per `Personal/AGENTS.md` (summarize;
never paste raw records/PII into chat or logs). The full model is `references/data-model.md`
(the canon); `schema.sql` is the structure.

</Goal>

<Scope>
<UseWhen>

- Resolve who a message is from (a Telegram/GitHub handle or a name) → `pp whois <q>`.
- Look up a person's languages, contacts, nationality, timezone, or project roles.
- Add or update a person, alias, contact, language, nationality, tag, or relationship.
- Re-sync project memberships after the projects registry changes (`pp import-projects`).

</UseWhen>
</Scope>

<Engine>

All operations go through `${HERMES_SKILL_DIR}/scripts/pp` (Python stdlib, no deps);
defaults to `--root ~/Workspaces/Personal/People`. Pass `--help` to any subcommand.

```
# read
pp whois <handle|name>                  # resolve -> person_id (+ aliases, contacts, comms, memberships)
pp show --id <id> ; pp list [--status|--kind|--project] ; pp search <q>
# manage a person (stable bare-slug id == the person_id consumers use)
pp upsert-person --id <id> --name "..." [--residence MY] [--preferred-language ja]
                 [--alias ...] [--language ...] [--nationality ...] [--timezone Asia/Tokyo]
pp set-status --id <id> --status active|inactive      # don't delete inactive people
pp review ; pp confirm|ignore --id <id>               # review_status (id never changes)
pp rename-person --old <id> --new <id>                # FK-safe
pp merge-person  --old <id> --into <id>               # FK-safe dedupe
# facets
pp alias-add|alias-rm   --id <id> --alias "..." [--primary]
pp contact-set|contact-rm --id <id> --channel telegram --handle "@h" [--primary]
pp lang-add|lang-rm --id <id> --language ja [--proficiency native] [--primary]
pp nat-add|nat-rm   --id <id> --country JP [--primary]
pp note-add --id <id> --text "..." ; pp tag-set|tag-rm --id <id> --axis comms --value "..."
pp rel-add|rel-rm --from <id> --to <id> --type colleague [--note "..."]
# data ops
pp import-projects                       # rebuild the membership mirror (calls `pj members --json`)
pp validate ; pp export --format both ; pp backup [--keep N]
pp init [--seed] [--force] ; pp import-json [--src DIR] ; pp migrate ; pp audit [--id <id>]
```

</Engine>

<Rules>

- Person `id` is a **bare lowercase slug** (e.g. `oy`, `master`) — it equals the `person_id`
  that `Projects/*/teams/members/` and `household-budget.counterparties.person_id` reference.
  Keep it stable; state lives in `review_status` / `status`, never in the id.
- **Don't guess personal facts.** Use `null` / omit when unknown (e.g. a multilingual
  person's `preferred_language` stays null until told). Set `review_status = needs_review`
  when unsure; never delete — `set-status --status inactive`.
- **Memberships are a mirror.** The **projects registry** (the `projects` skill / `pj`) is the
  source of truth; `pp import-projects` calls `pj members --json` and regenerates
  `person_project_memberships` (+ children). Don't hand-edit the mirror.
- **Privacy.** Sensitive channels (`phone`, `email`) are flagged `is_sensitive` and not
  populated by default. Never store gov IDs, home addresses, secrets, or wallet keys.
- Don't hand-edit `people.db` or the mirror — use `pp`. Schema evolves via `migrations/`
  (`pp migrate`), never `init --force` on a live DB. Summarize results to chat; no external
  sends without an explicit OK.

</Rules>

<Consumers>

- **household-budget** — `counterparties.type='person'` rows carry `person_id` referencing
  People (link a reimbursement/shared expense to a person).
- **message-reply** — resolves the sender (`pp whois`), then drafts in their
  `preferred_language` with tone from `working_relationship` + comms tags and scope from
  `permissions`.
- **Cross-store checks** — each store calls the others' **CLI** read-only (never opens another
  store's DB/files): `pp validate` calls `pj members` + `hb counterparties`; `hb validate` calls
  `pp list`; `pj validate` calls `pp list` + `hb projects`. A producer answers with a versioned
  JSON envelope; every check skips with a warning if the sibling CLI is unavailable. See
  `skills/workspaces/_cross.py` (the shared contract/resolver). A skill never calls another's `validate`.

</Consumers>
