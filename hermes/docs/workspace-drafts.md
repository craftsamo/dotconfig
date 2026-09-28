# Workspace drafts

Read-only view of the drafts under `~/Workspaces`, for the Assistant, Engineer
and people. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## The rule it reads

The layout rule is owned by `~/Workspaces/AGENTS.md` "Drafts" (private
overlay), which the Assistant reads at runtime: a file's location is its status.
Everything under an `.agent/` is a draft; canon is only a Group's `docs/`,
`data/`, `assets/` or repository. One job is one directory
`<Group>/.agent/<YYYYMMDD>-<job>/` (the root `~/Workspaces/.agent/` when no
single Group owns it), promoted into canon only on the user's approval and then
deleted. There is no job record or state file, so a draft that remains is work
not yet promoted; this list is the only index of open work.

## Shape

| Piece | Home | Reader |
|---|---|---|
| Lister, text output, CLI | `plugins/workspace-drafts/drafts.py` | all |
| `workspace_drafts` tool and `/drafts` | `plugins/workspace-drafts/__init__.py` | Engineer, Assistant |
| Launcher | `../bin/ws-drafts` | people, cron |

Stdlib only, loaded by path, so the tool, the launcher and cron run the same code.

## What it reports

- Areas: `~/Workspaces/.agent/`, each `{Projects,Personal}/<Group>/.agent/`, and
  the earlier layout (root `.scratch/`, `.deliverables/`, `.notes/`; in-Group
  `.agent/{scratch,deliverables,notes}/`) as `layout: legacy`. That layout was
  retired on 2026-09-28; it stays in the scan so that a job still finishing
  there, or anything written there again, shows up. Each immediate
  entry is one draft. `.inbox/` and canonical directories are never listed.
- Per draft: Group, start date from the name, bytes, file count, newest file
  change and idle days. Flags: `stale` (no file changed for `stale_days`,
  default 14), `misnamed` (not `<YYYYMMDD>-<kebab-slug>`), `legacy`.
- Metadata only: it never opens a file, never follows a symlink and never moves
  or deletes anything. Promotion and deletion stay with the Assistant under the
  rule above. Every result carries `source`, `status` and `diagnostics`; an
  unreadable directory is disclosed as `partial`.

## Everyday use

- `ws-drafts` — per-Group summary; `ws-drafts list [--group G] [--stale]
  [--misnamed] [--legacy] [--sort idle|size|name|started] [--json]`.
- `/drafts [stale|misnamed|legacy|<group>]` in Engineer and Assistant sessions
  (Telegram included) answers without a model turn as plain Markdown: an
  overview table, then one folded `<details>` section per place (current or
  an earlier-layout area) with a Draft / Idle / Size table. Chats with
  Telegram rich messages (the Assistant's) render the tables and folds;
  elsewhere they degrade to plain lines. Telegram has no argument
  completion, so a Group name matches case-insensitively by name, then prefix,
  then substring (`/drafts tech`), an unknown name answers with the choices,
  and the summary folds a tap-to-copy `/drafts <Group>` list. `/drafts` and
  `/activity` are in the Engineer and Assistant command menus.
- Enabled per profile: plugin `workspace-drafts`, toolset `workspace_drafts`
  (never on `a2a`); registration is limited to Engineer and Assistant in code.
