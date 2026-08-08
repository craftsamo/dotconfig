# Engineering QA — acceptance ladder

The verification side of close-out; the operations stay in
`../../execute/engineering/github-ops.md`. Verify BEFORE the
corresponding operation or relay — never after the fact.

## Merge readiness — before asking the user

Merge is user-gated; verify the layer is actually mergeable before
relaying the ask:

- CI is green on the PR (`gh pr checks`) — "was green locally" is
  not CI.
- The PR body carries `Closes #n` for its purpose Issue (missing →
  the engineer fixes the body in-session, per close-out).
- Review threads are resolved or explicitly deferred with the user.
- For a stack: this is the bottom unmerged layer, its base is the
  default branch, and the upper layers are named in the relay.

Presenting the merge ask WITH this evidence (checks state, diff
target, what it closes) is the relay — the user's go decides the
merge, it never substitutes for discovering the state.

## After the merge

- The PR is merged and the Issue actually closed (auto-close can
  miss when the merge base isn't the default branch).
- Remaining stack layers were retargeted/rebased by the engineer in
  the next turn (github-ops merge rule) — verify before releasing
  the next unit against the updated default branch.

## Purpose acceptance

A purpose is accepted when every done criterion in its Issue body
is evidenced across its 1–3 PRs — tie each criterion to a
gate-passed unit report; a criterion nothing evidences means the
purpose is NOT done regardless of merged PRs. Then (ops, direct):
sub-issue ticked, board item moved — and verify the tick and board
state match reality.

## Epic close

- Every purpose sub-issue is closed — none orphaned, none silently
  descoped (a dropped purpose is a user decision, recorded on the
  epic).
- The Roadmap board mirrors the final state.
- The epic's own goal statement is satisfied by the merged whole —
  read it once against reality before declaring the epic done.
