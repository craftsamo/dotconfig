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

Merge only on the user's explicit go — asked with readiness
verified per `../../quality-assurance/engineering/acceptance.md` —
never autonomous, never the engineer's. After merging a stack
layer, tell the engineer in the
next turn so the remaining layers are rebased/retargeted in-session;
the next unit is released against the updated default branch.

## Repo lifecycle — bootstrap steps

Decisions arrive fixed from `../../plan/engineering/bootstrap.md`
(sanctioned by the plan approval); execute them in this order. The
GitHub/registry steps are never delegable; only worktree-side
establishment inside the clone (step 3a) may go to the engineer
under an explicit, user-sanctioned `B1`/`B2` grant (`B1` =
scaffolder/skeleton/deps + initial commit in the clone, `B2` = +
push to the existing `origin` — repo creation is never the
engineer's):

1. **Group missing** → the private `scaffold` skill's
   `ws-new.sh group projects <Group>` (dirs + group `AGENTS.md` +
   registry row).
2. **Create on GitHub first**, per the sanctioned History posture:
   - Template starter (squashed start) →
     `gh repo create <owner>/<repo> --private --template <starter>`.
   - Plain starter (history kept) → clone the starter to the target
     ghq path, then `gh repo create <owner>/<repo> --private
     --source <path> --push` (repoints `origin` at the new repo) and
     `git -C <path> remote add upstream <starter-url>` — the
     derivative stays wired to its family.
   - Scratch → `gh repo create <owner>/<repo> --private` bare.
   Never `ws-new.sh repo` — its local `git init` bypasses the ghq
   layout and leaves an unlinked, remoteless repo.
3. **Clone via ghq** (template/scratch paths): `ghq get
   <owner>/<repo>` → `~/ghq/github.com/<owner>/<repo>`.
   3a. *(optional, granted)* — a scaffolder-based skeleton
   (`create-next-app`, `cargo new`, `uv init`, …) inside the clone
   is an engineer `B1`/`B2` job; release it as a unit with the
   target path and the named scaffolder.
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
