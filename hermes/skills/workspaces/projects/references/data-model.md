# Projects registry — data model (the canon)

SQLite v1, engine `pj` (stdlib only). Source of truth at
`~/Workspaces/Projects/.registry/projects.db`; `.registry/export/` is a regenerable mirror;
`.registry/backups/` holds timestamped `.db` snapshots + `legacy_archive/` (the pre-rebuild
`teams/members/*.json` + group docs). `schema.sql` is the authoritative structure.

## Principles
- **Stable, state-free ids.** A project `id` == the `Projects/<id>` directory name
  (e.g. `ExampleProject`). It is the cross-system join key. State lives in
  `review_status` (`needs_review|confirmed|ignored`) and `status` (`active|inactive|archived`),
  never in the id. `rename-project` rewrites all registry FKs in one transaction.
- **One central registry** for all groups (not one DB per group): people span projects, so a
  single DB with a `project_id` column makes cross-project queries and person joins trivial.
- **person_id is not a SQL FK.** Persons live in People's separate DB. Cross-domain checks go
  through the People CLI (`pp`), read-only — never by opening `people.db`. See `_cross`.
- **Versioned** (`user_version`); evolve via `migrations/`, never a destructive rebuild.

## Tables
### Identity
- **projects** `{id (==dir name), slug (lower-kebab), canonical_name, kind
  (org|client|category|personal|external), status, dir_path (NULL for external), summary,
  review_status, last_updated, created_at, updated_at}`.
- **project_aliases** `{project_id, alias, alias_norm (NFKC+casefold), is_primary}` — searchable
  names; how the budget's `proj_*` aliases reconcile (e.g. `EX`, `Example Org`, observed typos).
- **project_links** `{project_id, kind (landing|x|github|docs|discord|other), url, label}` —
  official public URLs (sourced from `docs/about/official-links.md`).

### Repos (github wiring)
- **repos** `{project_id, name, owner, host (github.com), url, ghq_path, link_path,
  has_agents_md, summary, status (declared|linked|missing|archived), review_status}`.
  `repo-set` records identity; `link-repo` creates `Projects/<group>/github/<name>` →
  `~/ghq/<host>/<owner>/<name>` symlink when a clone exists (status→`linked`), else `missing`.

### Memberships (SOURCE OF TRUTH — was `teams/members/*.json`)
1:1 with People's mirror tables, so `pj members` reproduces the exact shape People consumed.
- **memberships** `{project_id, person_id, status, working_relationship, can_merge, can_deploy,
  last_updated, created_at, updated_at}`.
- children: **membership_roles**, **membership_responsibilities**, **membership_areas**,
  **membership_permission_scopes** `{action: approve|review, target}`, **membership_notes**
  `{seq, text}`, **membership_contacts** `{channel, handle}` (project_contacts).
- `person_id` references People `persons.id` (validated through `pp`, not a SQL FK).

### Flexible tags (extensibility)
- **project_tag_axes** `{axis, label, review_status}` — new axis = one row (stage, priority,
  domain, engagement, comp_model, …). Same axis registry serves both scopes.
- **project_tags** `{project_id, axis, value, value_norm}` — tag a project.
- **membership_tags** `{project_id, person_id, axis, value, value_norm}` — tag a person×project.
- Report across either scope with `pj report --by <axis> [--scope project|member|both]`.

### Audit / views
- **project_audit** `{seq, ts, action, tbl, entity, field, old_value, new_value, note}` — git-less
  change history (`entity` = project_id, `<project_id>/<person_id>`, or repo name).
- **v_active_projects**, **v_project_member_counts**.

## member JSON ⇄ tables (round-trip)
`pj members --json` / `pj export` reconstruct one record per membership:

| JSON field | source |
|---|---|
| `project_id` / `person_id` / `status` / `working_relationship` | `memberships.*` |
| `roles[]` / `responsibilities[]` / `areas[]` | `membership_roles` / `_responsibilities` / `_areas` |
| `permissions.can_approve[]` / `can_review[]` | `membership_permission_scopes(action, target)` |
| `permissions.can_merge` / `can_deploy` | `memberships.can_merge` / `can_deploy` |
| `project_contacts{}` | `membership_contacts` |
| `notes[]` | `membership_notes` |
| `tags[]` | `membership_tags` |
| `last_updated` | `memberships.last_updated` |

Verified: rebuilding People's membership mirror from `pj members` is byte-equivalent to the old
`teams/members/*.json` source (0 semantic diffs).

## Cross-skill contract (`skills/workspaces/_cross.py`)
- `contract_version = 1`. Envelope: `{"contract_version":1,"skill":"<name>","data":{…}}`.
- Resolution: env `<CLI>_BIN` → `workspaces/cross.json` → convention `workspaces/<name>/scripts/<cli>`.
- **pj exposes (producer):** `projects`, `members`, `repos`, `links` (each `--json`).
- **pj consumes (consumer):** `pp list --json` (person existence) and `hb projects --json`
  (reconcile every budget `proj_*` to a registry project via `dir_path`/aliases).
- Consumers skip-with-warning on absence/error/version skew; never call a sibling's `validate`.

## Cross-store reconciliation map
```
People.person_project_memberships  ←(pj members --json)←  projects.memberships   [person_id]
HouseholdBudget.projects.proj_*    →(hb projects --json)→  projects.{dir_path,aliases}
HouseholdBudget.counterparties     →(hb counterparties)→   (type=person ⇒ People.persons.id)
```
