# Engineering capability — plan / execute / qa

Load when the work touches code: repos, builds, debugging, tests, PRs,
project boards. The specialist is the **engineer** resident session, which
drives OpenCode on the repo; GitHub bookkeeping stays with the assistant.

## Plan

Ground every implementation plan in the repo before promising anything:

1. **Locate the repo** (Step 2): `pj show <Group>` → the
   `~/Workspaces/Projects/<Group>/github/<repo>` path. No repo yet →
   bootstrap is part of the plan (engineer creates it; you register it
   with `pj repo-set` + `pj link-repo` afterwards).
2. **Establish the base plan session yourself** — an OpenCode plan run in
   the repo, read-only by the plan agent's own permissions:

   ```bash
   cd <repo> && opencode run --auto --agent plan --title "waves: <goal>" \
     'Split this goal into WAVES only — coarse milestones and their
      dependency order, one line each. No phase/unit detail.
      <goal, constraints, done criteria>'
   ```

   Recover the session id (`opencode session list`). This base session —
   not a prose summary — is what the engineer will detail and implement,
   so the outline stays grounded and nothing is lost in translation.
3. **Approve with the user** — present the Wave outline in plain language
   (what lands, in what order, what it costs) plus the Authority the work
   needs (`A1` commit-only default; `A2` push + PR only when the user
   wants a PR; `A3` + dependency changes). One `clarify`.
4. Requirement decomposition for issue-tracked repos ("login feature" →
   epic + sub-issues) is also planned here: the engineer session drafts
   the split (draft-only), the user approves it, and **you** register the
   Issues via `gh` — see GitHub ops below.

Small settled fixes ("fix the off-by-one in `foo()`, test is
`bar_test.py`") skip the base session: state the intent and go straight to
Execute.

## Execute

Start the engineer resident session with the SessionBrief plus:

- `Repo:` the absolute worktree path (the engineer works in place; it may
  create its own worktree for isolation when parallel work demands it).
- `Base session:` the OpenCode plan-session id from Plan (when one
  exists). The engineer forks it per Wave — detail-planning and
  implementation happen inside OpenCode under the engineer's own
  discipline (decompose → confirm → build; PermissionBridge; model
  ladder).
- `Issue: #n` when the work implements a registered Issue — the Issue text
  is the outline; no base session needed.
- `Authority:` the sanctioned preset + `scope:` / `do not touch:`
  boundaries. The engineer translates it into OpenCode permission denies;
  anything outside the grant comes back as a question in its reply.

Supervision:

- The engineer reports per Wave: what landed, verification output, open
  questions. Answer in-plan questions yourself in the next turn; relay the
  rest.
- Course corrections are conversational turns ("そのスキーマはBにして",
  "Wave 2 の前にテストを先に"). The session holds the repo context.
- Long builds are normal — turns run in background; the completion
  notification wakes you.

## QA

- The engineer's own loop already verifies each Wave (repo checks +
  OpenCode review agent) — do not re-review diffs line by line.
- Your gate is outcome-level: the reported check/test output is actual
  (not claimed), the deliverable matches the plan's done criteria, nothing
  out of scope changed (`git -C <repo> status` / `log --oneline` spot
  check), and for UI work a rendered screenshot exists.
- Defects → feedback turn into the same session. Accepted → GitHub ops
  below, then `close`.

## GitHub ops — assistant-owned

Issue registration, board sync, and merges are **your** job, through your
own `gh`, after the relevant approval — the engineer never needs
issue-write grants and never merges:

- Register an approved decomposition: `gh issue create` per sub-issue
  (epic linked), then keep board state in sync.
- PRs: at `A1` the engineer only commits — you push/open the PR yourself
  if the user wants one; at `A2` the engineer opens its own PR and
  responds to reviews inside the session.
- Merge only on the user's explicit go; merging is never autonomous and
  never the engineer's.

## Pitfalls

- Promising an implementation plan that no OpenCode plan session grounded.
- Handing the engineer a prose plan when a base session id exists — the
  session is the handoff, prose drifts.
- Writing `A2`/`A3` grants the user never sanctioned, or letting a session
  widen its own grant.
- Re-planning inside chat what the engineer's decompose step will do
  better against the live worktree.
- Merging, or letting any session merge, without the user's explicit go.
