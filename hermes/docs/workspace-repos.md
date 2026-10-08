# Workspace repos

Read-only view of the repositories under `~/Workspaces` — their local Git state
and their open GitHub work — for the Assistant and people. Part of
the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## What counts as a repository

Every entry of `~/Workspaces/<Area>/<Group>/github/` (Area is `Projects` or
`Personal`), usually a symlink to a `~/ghq` clone. The Group is the directory
above `github/`; the GitHub repository is the one `origin` points at.

## Shape

| Piece                                   | Home                                  | Reader              |
| --------------------------------------- | ------------------------------------- | ------------------- |
| Scanner, GitHub query, text output, CLI | `plugins/workspace/workspace-repos/repos.py`    | all                 |
| `workspace_repos` tool and `/repos`     | `plugins/workspace/workspace-repos/__init__.py` | Assistant           |
| Launcher                                | `../bin/ws-repos`                     | people, cron        |

Stdlib plus the `git` and `gh` binaries, loaded by path, so the tool, the
launcher and cron run the same code.

## What it reports

- Local state, from Git's own refs with optional locks off: it never fetches,
  pulls, pushes, commits or refreshes the index, so `behind` is as of the last
  fetch. Flags: `broken` (link target missing), `not-git`, `no-remote`,
  `dirty` (changed or untracked files), `unpushed` (commits on any local branch
  that no remote branch contains), `no-upstream`, `behind`, `detached`, `stash`,
  `worktrees` (more than one), and `shared-origin` (two local repos push to one
  GitHub repo, almost always a misconfigured `origin`).
- GitHub, in one GraphQL query through `gh`: open PR, issue and discussion
  counts per repository; for `prs` and `issues` also the open items (review
  requested from you, CI state, review decision, assignees, idle days).
  `remote-missing` flags an `origin` GitHub cannot resolve; `read-only` flags a
  repository you cannot push to (an upstream clone), whose PRs and issues are
  neither counted nor listed. A GitHub repository counts once however many
  local clones point at it.
- A period — `today`, `week` (7 days), `month` (30 days) or N days, counted in
  local calendar days like `/activity` — turns `prs` and `issues` into every
  item updated in it, merged and closed included (up to 50 per repository,
  disclosed as `partial` beyond), and drives `commits`: your commits (author
  equal to the repo's Git `user.name` or `user.email`, bots and merges
  excluded) on local and remote-tracking branches, newest first, as of the
  last fetch and without network. A commit reached from two clones of one
  GitHub repository counts once; a pushed commit links to GitHub.
- Items are fetched only for repositories you can write to, four per query in
  parallel, after one query for the counts: a single query for every item
  timed out on GitHub.
- The repos needing attention are those with any flag except `behind`,
  `detached` and `read-only`.
- When `gh` fails (not logged in, offline), the local state is still returned
  and the result is `partial`; a remote GitHub cannot find is a finding, not a
  failed read. Every result carries `source`, `status` and `diagnostics`.

Discussions stay a count: there are too few to list. GitHub Projects are not
read here; the board has its own tools (`github_project_*`).

## Everyday use

- `ws-repos [--group G] [--no-github] [--json]`,
  `ws-repos prs|issues|commits [--period today|week|month|N] [--group G]`.
- `/repos [prs|issues|commits] [today|week|month|N] [<group>]`, words in any
  order (`/repos commits week tech`); `commits` alone means today, and a
  period without `commits`, `prs` or `issues` answers with those three. In
  Assistant sessions (Telegram included) answers without a model
  turn as plain Markdown, like `/drafts`: a per-Group table (one Group: per
  repo), the repos needing attention folded, and for `prs` / `issues` /
  `commits` one folded section per repository with linked items. A Group name
  matches case-insensitively by name, then prefix, then substring
  (`/repos prs tech`); an unknown name answers with the choices, and every answer folds
  tap-to-copy next commands. `pr`, `pulls` and `pullrequests` are accepted for
  `prs`, `commit` and `log` for `commits`. `/repos` is in the
  Assistant command menu.
- Enabled per profile: plugin `workspace-repos`, toolset `workspace_repos`
  (never on `a2a`); registration is limited to the Assistant in code.
