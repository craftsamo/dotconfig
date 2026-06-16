# Projects — git-managed code (grouped) + a central registry

Each subdirectory is a **group** (org / client / category) == a project id (the dir name,
e.g. `ExampleProject`), which is the cross-system join key. A group holds:
- `github/<repo>/` — the repos, flat under `github/` (the group is the owner; usually a
  symlink to a `~/ghq` clone). Each repo owns a committed, **tool-agnostic** `AGENTS.md`
  (architecture, build/test/run, conventions) — shared context for every agents.md-aware tool
  (Hermes coder, OpenCode, Codex, Cursor). Keep tool-specific instructions out of it.
- `docs/` — design notes, specs, prose project knowledge (`docs/about/`). Not in the registry DB.
- `data/` — datasets (optional; created only when a group actually has data).

Structured facts about groups — **identity (slug/aliases/dir_path), repos, official links,
team memberships, and flexible tags** — live in the **central registry**, not in loose files:
- `.registry/projects.db` — **SQLite (schema v1), the source of truth**, operated only via the
  `projects` skill's `pj` CLI. `.registry/export/` is a regenerable JSON/CSV mirror; `.registry/
  backups/` holds DB snapshots + `legacy_archive/` (the pre-rebuild `teams/members/*.json` + docs).
- There is **no `teams/` directory** anymore — memberships are `pj member-set` / `pj members`.

## Engine
- All registry operations go through the `projects` skill: `pj show|list|members|repos|links`,
  `upsert-project`/`set-status`/`rename-project`/`merge-project`, facets (`alias-*`/`link-*`/
  `tag-*`), `repo-set`/`link-repo`, `member-set` (+ `mtag-*`), ops `validate`/`export`/`backup`.
  Don't hand-edit `projects.db` or the mirror. Full model: the `projects` skill's `data-model.md`.

## Cross-skill linkage (read each other's CLI, never the other's DB/files — see skills/workspaces/_cross.py)
- **People** rebuilds its membership mirror from `pj members --json` (`pp import-projects`);
  members reference People by `person_id`.
- **HouseholdBudget** `proj_*` masters reconcile to a registry project by `dir_path`/aliases;
  `pj validate` flags budget projects with no registry match.

## How to work
- Coordinate: create a kanban task referencing `Projects/<Group>/github/<repo>`; coder
  worktrees from it. Don't do large refactors inline in chat.
- Don't commit/push without the human's go-ahead. Throwaway work goes in `../.scratch/`.
- Add a group/repo with the `workspace-scaffold` skill: `ws-new.sh group projects <Group>`
  (registers it in the registry) then `ws-new.sh repo <Group> <repo>`.
