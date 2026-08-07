# Engineering — GitHub ops (assistant-owned)

Boundary-time operations: everything that happens around and between
units, none of it the engineer's. One rule decides the vehicle:
**codebase-dependent writes run through OpenCode; pure bookkeeping is
your direct call.**

| Through OpenCode (needs worktree + conventions) | Direct (`gh` / `ghq` / `pj`) |
| --- | --- |
| commit, push, PR creation/upkeep | merge (user-gated) |
| Issue/epic drafting + registration | Roadmap board status sync |
| | repo lifecycle (create / clone / registry) |

OpenCode runs happen in the repo (`cd <repo> && opencode run --auto
'<ask>'`); its git/PR/issue skills own conventions, links, and body
formats. Never hand-write a PR or Issue with raw `gh`.

## Register the approved decomposition

Purpose-unit work, once the user approves the plan: run OpenCode in
the repo to create the epic + purpose sub-issues from the approved
decomposition — bodies grounded in the codebase. Then sync the
user's Roadmap board directly. The engineer never registers Issues.

## PRs

- `A1`: the engineer only commits — the PR, when the user wants one,
  is yours (close-out below).
- `A2`: the engineer pushes its branch and maintains its own PR
  through OpenCode — a multi-PR purpose grows as a stack, one layer
  at a time — and responds to reviews inside the session.

## Unit close-out — after the QA gate passes

- **Purpose unit**: confirm the PR(s) carry `Closes #n` (missing →
  have the engineer fix the PR body in-session); tick the epic's
  sub-issue state and move the board item directly. Merge waits for
  the user's go.
- **A1 work where the user wants a PR**: the engineer only
  committed — run OpenCode yourself in the repo to push the branch
  and open the PR.
- **Wave unit**: verify the commit landed per the report; nothing
  external to sync.

## Merge — user-gated, direct, yours

Merge only on the user's explicit go; never autonomous, never the
engineer's. After merging a stack layer, tell the engineer in the
next turn so the remaining layers are rebased/retargeted in-session;
the next unit is released against the updated default branch.

## Repo lifecycle — bootstrap steps

Decisions arrive fixed from `../../plan/engineering/bootstrap.md`
(sanctioned by the plan approval); execute them in this order.
Worktree-side establishment is delegable under an explicit,
user-sanctioned `B1`/`B2` grant — the GitHub/registry steps never
are:

1. **Group missing** → the private `scaffold` skill's
   `ws-new.sh group projects <Group>` (dirs + group `AGENTS.md` +
   registry row).
2. **Create on GitHub first**:
   `gh repo create <owner>/<repo> --private` — with
   `--template <starter>` when the chosen starter is a template
   repo, or from a plain starter clone via `--source … --push` plus
   an `upstream` remote (family wiring per starter-catalog). Never
   `ws-new.sh repo` — its local `git init` bypasses the ghq layout
   and leaves an unlinked, remoteless repo.
3. **Clone via ghq**: `ghq get <owner>/<repo>` →
   `~/ghq/github.com/<owner>/<repo>`.
4. **Register + link**:
   `pj repo-set --project <Group> --name <repo> --owner <owner>`,
   then `pj link-repo --project <Group> --name <repo>` —
   materializes the `Projects/<Group>/github/<repo>` symlink.
5. **Repo `AGENTS.md`** — seed from the scaffold template when the
   starter lacks one; fill with real, tool-agnostic facts
   (architecture, build/test/run, conventions) and commit it.
6. **Verify**: the symlink resolves, `.git` exists, starter files
   are present, `AGENTS.md` is filled (not the stub).

Deploy credentials go through the Keychain shims — never a committed
`.env`.
