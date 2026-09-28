# Workspace repos

Read-only view of the repositories under `~/Workspaces` — their local Git state
and their open GitHub work — for the Assistant, Engineer and people. Part of
the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## What counts as a repository

Every entry of `~/Workspaces/<Area>/<Group>/github/` (Area is `Projects` or
`Personal`), usually a symlink to a `~/ghq` clone. The Group is the directory
above `github/`; the GitHub repository is the one `origin` points at.

## Shape

| Piece | Home | Reader |
|---|---|---|
| Scanner, GitHub query, text output, CLI | `plugins/workspace-repos/repos.py` | all |
| `workspace_repos` tool and `/repos` | `plugins/workspace-repos/__init__.py` | Engineer, Assistant |
| Launcher | `../bin/ws-repos` | people, cron |

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
- The repos needing attention are those with any flag except `behind`,
  `detached` and `read-only`.
- When `gh` fails (not logged in, offline), the local state is still returned
  and the result is `partial`; a remote GitHub cannot find is a finding, not a
  failed read. Every result carries `source`, `status` and `diagnostics`.

Discussions stay a count: there are too few to list. GitHub Projects are not
read here; the board has its own tools (`github_project_*`).

## Everyday use

- `ws-repos [--group G] [--no-github] [--json]`, `ws-repos prs|issues
  [--group G]`.
- `/repos [prs|issues] [<group>]` in Engineer and Assistant sessions (Telegram
  included) answers without a model turn as plain Markdown, like `/drafts`: a
  per-Group table (one Group: per repo), the repos needing attention folded,
  and for `prs` / `issues` one folded section per repository with linked
  items. A Group name matches case-insensitively by name, then prefix, then
  substring (`/repos prs tech`); an unknown name answers with the choices, and
  every answer folds tap-to-copy next commands. `pr`, `pulls` and
  `pullrequests` are accepted for `prs`. `/repos` is in the Engineer and
  Assistant command menus.
- Enabled per profile: plugin `workspace-repos`, toolset `workspace_repos`
  (never on `a2a`); registration is limited to Engineer and Assistant in code.
