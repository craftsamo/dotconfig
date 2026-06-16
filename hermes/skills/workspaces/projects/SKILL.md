---
name: projects
description: >-
  Projects registry (SQLite v1) — the source of truth for the project groups under
  ~/Workspaces/Projects: identity (slug/aliases/dir_path), repos, official links, team
  memberships (the mirror People consumes), and flexible tags. Use to look up a project,
  its repos/links/members, see who works on what, or manage the registry. Keyed by the
  Projects/<id> directory name; consumed by people (pj members) and reconciled by
  household-budget (proj_* ↔ dir_path/aliases). プロジェクト, チーム, レポ, projects, repos.
version: 0.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [projects, registry, sqlite, repos, teams, memberships, directory]
    category: workspaces
---

# Projects

The registry of everything under `~/Workspaces/Projects`. The SQLite DB is the source of
truth at `~/Workspaces/Projects/.registry/projects.db`; JSON/CSV under `.registry/export/`
is a regenerable mirror. The full model is `references/data-model.md` (the canon);
`schema.sql` is the structure. Member calibration (`working_relationship`, notes) is
semi-private — summarize, don't dump raw; the DB lives outside any git tree.

## When to use
- Look up a project: its repos, official links, members, tags, directory → `pj show --id <P>`.
- Resolve who works on a project / which projects a person is on → `pj members [--project <P>]`.
- Add or update a project, repo, link, membership, or tag.
- Wire a repo's clone/symlink (`pj link-repo`), or reconcile against the budget (`pj validate`).
- Re-export the mirror after changes (`pj export`).

## Engine (run via the bundled CLI)
All operations go through `${HERMES_SKILL_DIR}/scripts/pj` (Python stdlib, no deps); defaults
to `--root ~/Workspaces/Projects`. Pass `--help` to any subcommand.

```
# read
pj show --id <P> [--json]            # full project (identity, aliases, links, repos, members, tags)
pj list [--status|--kind] ; pj report --by <axis> [--scope project|member|both]
pj projects [--json]                 # read-port: identity + aliases (budget/People reconcile)
pj members [--project <P>] [--json]  # read-port: memberships in People-mirror shape
pj repos [--project <P>] ; pj links [--project <P>]
# projects (stable id == the Projects/<id> dir name; state lives in review_status/status)
pj upsert-project --id <P> [--name ..][--slug ..][--kind ..][--dir-path ..|--external][--alias ..]
pj set-status --id <P> --status active|inactive|archived
pj review ; pj confirm|ignore --id <P>
pj rename-project --old <P> --new <P>     # FK-safe (then re-sync People + budget)
pj merge-project  --old <P> --into <P>     # FK-safe dedupe
# facets
pj alias-add|alias-rm --id <P> --alias "..." [--primary]
pj link-set|link-rm   --id <P> --kind landing|x|github|docs|discord|other --url "..."
pj tag-set|tag-rm     --id <P> --axis <a> --value "..."        # project tags (free axes)
# repos
pj repo-set --project <P> --name <r> [--owner ..][--url ..][--ghq-path ..][--status ..]
pj repo-rm  --project <P> --name <r> ; pj link-repo --project <P> --name <r>
# members + per-member free-axis tags
pj member-set --project <P> --person <id> [--role ..][--area ..][--responsibility ..]
              [--approve ..][--review ..][--note ..][--contact ch=handle][--can-merge][--can-deploy]
pj member-rm  --project <P> --person <id> ; pj mtag-set|mtag-rm --project <P> --person <id> --axis <a> --value "..."
# data ops
pj validate ; pj export --format both ; pj backup [--keep N]
pj init [--seed] [--force] ; pj import-legacy [--src DIR] ; pj import-json [--src DIR] ; pj migrate ; pj audit
```

## Rules
- A project `id` is the **`Projects/<id>` directory name** (e.g. `ExampleProject`) — the
  cross-system join key (People memberships' `project_id`; the budget reconciles its `proj_*`
  via `dir_path`/aliases). Keep it stable; state lives in `review_status`/`status`, never the id.
  `rename-project` rewrites registry FKs, then re-run People import + a budget reconcile.
- **Don't guess.** A project with no local directory is `--external` (`dir_path` NULL, e.g.
  `branaid` referenced only by the budget). Set `review_status = needs_review` when unsure.
- **Memberships are the source of truth here** (they used to live in `teams/members/*.json`).
  Manage with `member-set`; People rebuilds its mirror from `pj members --json`. Don't hand-edit.
- **Repos**: `repo-set` records identity; `link-repo` materializes the `github/<name>` symlink to
  a `~/ghq` clone (cloning itself is a separate, explicit step). `docs/about/` stays prose (not in the DB).
- Don't hand-edit `projects.db` or the mirror — use `pj`. Schema evolves via `migrations/`
  (`pj migrate`), never `init --force` on a live DB. Summarize results; no external sends without an OK.

## Cross-skill contract (see `skills/workspaces/_cross.py`)
Cross-domain reads call a SIBLING CLI — never open its DB/files, never call its `validate`.
Producers answer with a JSON envelope (`{contract_version, skill, data}`); consumers skip with a
warning on absence / error / version skew. `pj` exposes `projects`/`members`/`repos`/`links --json`;
it consumes `pp list --json` (person existence) and `hb projects --json` (budget reconcile).

## Consumers
- **people** — `pp import-projects` rebuilds its membership mirror from `pj members --json`
  (the registry is the source; People stores a regenerable mirror, joined by `person_id`).
- **household-budget** — `projects.proj_*` reconcile to a registry project by `dir_path`/aliases;
  `pj validate` flags budget projects with no registry match (e.g. a new `proj_*` you haven't grouped).
