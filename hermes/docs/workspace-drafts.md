# Workspace drafts

Read-only view of the drafts under `~/Workspaces`, and of what waits in its
inbox, for the Assistant and people. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## The rule it reads

The layout rule is owned by `~/Workspaces/AGENTS.md` "Drafts" (private
overlay), which the Assistant reads at runtime: a file's location is its status.
Everything under an `.agent/` is a draft; canon is only a Group's `docs/`,
`data/`, `assets/` or repository. One job is one directory
`<Group>/.agent/<YYYYMMDD>-<job>/` (the root `~/Workspaces/.agent/` when no
single Group owns it), promoted into canon only on the user's approval and then
deleted. There is no job record or state file, so a draft that remains is work
not yet promoted; this list is the only index of open work.

The same file makes `~/Workspaces/.inbox/` the place for unsorted incoming
material, triaged into a Group or a draft job and kept near-empty. Tools that
fetch files land them there (`.inbox/google`, `.inbox/signal`), so it fills
without anyone deciding to.

## Shape

| Piece                                 | Home                                   | Reader              |
| ------------------------------------- | -------------------------------------- | ------------------- |
| Lister, text output, CLI              | `plugins/workspace/workspace-drafts/drafts.py`   | all                 |
| `workspace_drafts` tool and `/drafts` | `plugins/workspace/workspace-drafts/__init__.py` | Assistant           |
| Launcher                              | `../bin/ws-drafts`                     | people, cron        |

Stdlib only, loaded by path, so the tool, the launcher and cron run the same code.

## What it reports

- Areas: `~/Workspaces/.agent/`, each `{Projects,Personal}/<Group>/.agent/`, and
  the earlier layout (root `.scratch/`, `.deliverables/`, `.notes/`; in-Group
  `.agent/{scratch,deliverables,notes}/`) as `layout: legacy`. That layout was
  retired on 2026-09-28; it stays in the scan so that a job still finishing
  there, or anything written there again, shows up. Each immediate
  entry is one draft. Canonical directories are never listed, and the inbox
  is never a draft (below).
- Per draft: Group, start date from the name, bytes, file count, newest file
  change and idle days. Flags: `stale` (no file changed for `stale_days`,
  default 14), `misnamed` (not `<YYYYMMDD>-<kebab-slug>`), `legacy`.
- **The inbox, apart.** `summary` adds an `inbox` block (items, size, stale,
  oldest, per source) unless it is narrowed to a Group; `inbox` lists the items. `scan()` — what work reports
  read — never includes it, so incoming files are never counted as open work.
  One item is an entry of `.inbox/<source>/` (any real directory directly in
  `.inbox/` is a source, a hand-made folder included), or a loose entry
  directly in `.inbox/` (source `(loose)`); a directory item is measured at any
  depth. Per item: source, bytes, file count, the oldest and the newest file's
  date. `stale` means the oldest file has waited `inbox_stale_days` (default
  7, shorter than drafts because the inbox is to stay near-empty); judging by
  the oldest file means adding a file never hides one that has waited. Waiting
  is read from file modification times, which the fetch tools set when they
  save; a file copied in with its original time kept looks older. A
  missing inbox, or one that is a symlink, is empty; `group` and `layout` do
  not apply, and `stale` is its only flag.
- Metadata only: it never opens a file, never follows a symlink and never moves
  or deletes anything. Promotion and deletion stay with the Assistant under the
  rule above. Every result carries `source`, `status` and `diagnostics`; an
  unreadable directory is disclosed as `partial`.

## Everyday use

- `ws-drafts` — per-Group summary with an inbox line;
  `ws-drafts list [--group G] [--stale] [--misnamed] [--legacy] [--sort idle|size|name|started] [--json]`;
  `ws-drafts inbox [--stale] [--inbox-stale-days N] [--sort idle|size|name] [--json]`,
  oldest first.
- `/drafts [inbox|stale|misnamed|legacy|<group>]` in Assistant sessions
  (Telegram included) answers without a model turn as plain Markdown: an
  overview table, then one folded `<details>` section per place (current or
  an earlier-layout area) with a Draft / Idle / Size table. `/drafts inbox`
  has a Source table and one fold per source with an Item / Waiting / Size
  table; the word `inbox` wins over a Group of that name. The summary shows
  an Inbox line and folds `/drafts inbox` with the other copyable commands. Chats with
  Telegram rich messages (the Assistant's) render the tables and folds;
  elsewhere they degrade to plain lines. Telegram has no argument
  completion, so a Group name matches case-insensitively by name, then prefix,
  then substring (`/drafts tech`), an unknown name answers with the choices,
  and the summary folds a tap-to-copy `/drafts <Group>` list. `/drafts`,
  `/repos` and `/activity` are in the Assistant command menu.
- Enabled per profile: plugin `workspace-drafts`, toolset `workspace_drafts`
  (never on `a2a`); registration is limited to the Assistant in code.
