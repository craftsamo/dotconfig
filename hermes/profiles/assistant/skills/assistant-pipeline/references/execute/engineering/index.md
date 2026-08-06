# Engineering — execute

The specialist is the **engineer** resident session, which drives
OpenCode on the repo; GitHub bookkeeping stays with the assistant.
Engineering is **resident-only**: no `card_units` — implementation is
never a card.

## Resident session

Start the engineer resident session with the SessionBrief plus:

- `Repo:` the absolute worktree path (the engineer works in place; it may
  create its own worktree for isolation when parallel work demands it).
- `Base session:` the OpenCode plan-session id from Plan (when one
  exists). The engineer forks it per Wave — detail-planning and
  implementation happen inside OpenCode under the engineer's own
  discipline (decompose → confirm → build; PermissionBridge; model
  ladder).
- `Issue: #n` when the work implements a registered Issue — the Issue
  text is the outline; no base session needed.
- `Authority:` the sanctioned preset + `scope:` / `do not touch:`
  boundaries. The engineer translates it into OpenCode permission denies;
  anything outside the grant comes back as a question in its reply.

Supervision:

- The engineer reports per Wave: what landed, verification output, open
  questions. Answer in-plan questions yourself in the next turn; relay
  the rest.
- Course corrections are conversational turns ("そのスキーマはBにして",
  "Wave 2 の前にテストを先に"). The session holds the repo context.
- Long builds are normal — turns run in background; the completion
  notification wakes you.

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

- Handing the engineer a prose plan when a base session id exists — the
  session is the handoff, prose drifts.
- Writing `A2`/`A3` grants the user never sanctioned, or letting a
  session widen its own grant.
- Re-planning inside chat what the engineer's decompose step will do
  better against the live worktree.
- Merging, or letting any session merge, without the user's explicit go.
