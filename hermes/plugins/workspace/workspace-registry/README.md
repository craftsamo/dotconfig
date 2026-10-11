# workspace-registry

People, projects, memberships and repositories of `~/Workspaces`, kept as CSV
files and reached through one Hermes tool (`workspace_registry`) and one thin
CLI (`wsreg`). Both run the same stdlib engine, `registry.py`.

One registry, no database, no migrations, no audit log. The source is public;
records, local integrations and historical data migration scripts are not.

## Setup

`bin/wsreg` loads this engine from the same dotconfig checkout. No private
overlay is required. Initialize your own empty records with `wsreg init`, then
add people/projects through the CLI or the Assistant's `workspace_registry`
tool. `WSREG_ROOT` sets the Workspaces root; `WSREG_DIR` overrides only the data
directory. Neither setting belongs in tracked configuration with real values.

## Files

```
~/Workspaces/.registry/          # the data (not tracked anywhere)
  persons.csv                    person identity
  person_aliases.csv             names a person is known by
  person_contacts.csv            channel handles (sender resolution)
  person_languages.csv
  person_nationalities.csv
  person_notes.csv               dated free text, file order kept
  projects.csv                   one row per Projects/<id> group (orgs included)
  project_aliases.csv
  project_links.csv              official URLs
  project_tags.csv               free axes (stage, priority, …)
  tag_axes.csv                   labels of the tag axes
  repos.csv                      repos belonging to a project
  memberships.csv                person × project
  membership_roles.csv
  membership_responsibilities.csv
  membership_areas.csv
  membership_notes.csv           file order kept
  .lock                          writer lock (flock)
```

All files are UTF-8 CSV with a header row. Empty cell = no value. Booleans are
`true` / `false` (reading also accepts `1`/`0`/`yes`/`no`/empty). A missing
file reads as an empty table. Hand edits are allowed; `validate` checks them.

### Columns

| File                                            | Columns (key in **bold**)                                                                                                     |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| persons                                         | **id**, display_name, kind, status, review_status, residence_country, preferred_language, preferred_contact_channel, timezone |
| person_aliases                                  | **person_id**, **alias**, is_primary                                                                                          |
| person_contacts                                 | **person_id**, **channel**, **handle**, is_primary                                                                            |
| person_languages                                | **person_id**, **language**, proficiency, is_primary                                                                          |
| person_nationalities                            | **person_id**, **country**, is_primary                                                                                        |
| person_notes                                    | person_id, date, text                                                                                                         |
| projects                                        | **id**, slug, canonical_name, kind, status, organization_id, summary, review_status                                           |
| project_aliases                                 | **project_id**, **alias**, is_primary                                                                                         |
| project_links                                   | **project_id**, **kind**, **url**, label                                                                                      |
| project_tags                                    | **project_id**, **axis**, **value**                                                                                           |
| tag_axes                                        | **axis**, label                                                                                                               |
| repos                                           | **project_id**, **name**, owner, host, url, ghq_path, summary, status, review_status                                          |
| memberships                                     | **project_id**, **person_id**, status, working_relationship, can_merge, can_deploy                                            |
| membership_roles / \_responsibilities / \_areas | **project_id**, **person_id**, **role** / **responsibility** / **area**                                                       |
| membership_notes                                | project_id, person_id, text                                                                                                   |

Aliases, handles and tag values are compared after normalization (NFKC,
casefold, collapsed spaces; handles also drop `@` and `t.me/`, `x.com/`,
`github.com/` prefixes).

### Derived, never stored

- `dir_path` of a project: `~/Workspaces/Projects/<id>` when that directory
  exists, else null.
- `ghq_path` of a repo: `$GHQ_ROOT` (default `~/ghq`) `/<host>/<owner>/<name>`.
  The column holds only an override that differs from that default.
- `link_path`: `<dir_path>/github/<name>`; `has_agents_md`: the clone has an
  `AGENTS.md`.

## Rules (enforced by validate)

- Person id: bare lowercase slug (`[a-z0-9][a-z0-9_]*`). Project id: the
  `Projects/<id>` directory name. Ids are stable; state lives in `status` and
  `review_status`.
- Enumerations: person kind `self|individual` (at most one `self`), person
  status `active|inactive`; project kind `org|client|category|personal|external`,
  status `active|inactive|archived`; repo status `declared|linked|missing|archived`;
  membership status `active|inactive`; review_status
  `needs_review|confirmed|ignored`; link kind
  `landing|x|github|docs|discord|other`; proficiency
  `native|fluent|conversational|basic`; channel
  `github|telegram|x|website|signal|matrix|discord|linkedin|email|phone`.
- Country codes are ISO 3166-1 alpha-2 (upper case), languages ISO 639-1/2
  (lower case), timezones IANA names.
- Every foreign key resolves: facets to their person or project, memberships to
  both, membership children to a membership, `organization_id` to a project of
  kind `org` other than itself.
- At most one primary alias, language, nationality and contact per owner.
- No duplicate keys (after normalization).

Warnings (reported, never blocking): an alias shared by two owners, a tag axis
missing from `tag_axes.csv`, a `Projects/<dir>` with no registry row, an
`external` project that has a directory, and any checks supplied by a local
integration.

### Optional local integration

An ignored `peer_checks.py` beside `registry.py` can supply two functions:
`validate_warnings(reg, norm) -> list[str]` and
`rename_note(kind, old, new) -> str | None`. It is installed by the machine's
maintainer, never selected through tool arguments. It may be a symlink to
private code; that code must derive its own resources from its resolved path.
Checks read other stores but never modify them.

Without this file, only the registry's own checks run. A broken installed link,
invalid interface or execution failure is reported in `warnings` (also on CLI
stderr), not silently treated as absence. It does not roll back a valid write.
The peer's failures remain warnings; `ok` is determined by registry errors.

## Writes

Every write takes the lock, loads everything, applies the change, validates,
and writes only the changed files (temp file + rename). A write is rejected
when it would add a validation error; errors that were already present (a
broken hand edit) are reported as warnings and do not block unrelated writes.
People and projects are never deleted through the tool — set `status`.

## New Groups

`group_create` (`wsreg group-create`) is the one way to start a Group: it validates the
project row first, then makes `Projects/<id>/{github,docs,data}`, seeds `AGENTS.md` from
`templates/group.AGENTS.md` (never overwriting one) and writes the row. `org` and
`external` projects have no directory; register them with `project_set`. Repos are
`~/ghq` clones linked with `repo_set` + `link_repo` (or `wslink`), never created here.
A Personal group is just `Personal/<Group>/{data,docs}` made by hand, never under git.

## Interfaces

- **Tool** `workspace_registry` (Assistant): `action` + parameters; see
  `DESCRIPTION` in `__init__.py`. Inbound A2A requests are refused.
- **CLI** `wsreg <action> [--key value]…` prints JSON. Read actions print the
  cross-skill envelope `{"contract_version": 1, "skill": "registry", "data": …}`
  for consumers of `persons` / `projects`; `wslink` reads `projects` / `repos`.
  `--root <dir>` points at another Workspaces root (tests, staging).

## Tests

`hermes-python --test -m unittest discover -s hermes/plugins/workspace/workspace-registry/tests`
