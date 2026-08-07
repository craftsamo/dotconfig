# Delivery — GitHub flow and the evidence-backed handoff (engine)

Load this when the work leaves the worktree: committing, pushing, PRs,
Issue/board interaction, responding to review, and assembling the final
report. Execution goes through OpenCode; **auditing the result is yours**
(`references/verify.md` V6). The core file's Authority contract decides what
is allowed at all.

## GitHubFlow

Your GitHub write surface is what the Authority grant covers — commits,
branch push, and your own PR at A2/A3; **Issue registration, board
writes, and merges belong to the assistant**, never to you. Every granted
write goes **through OpenCode**, never through your own `gh` calls —
OpenCode owns the repo's conventions via its skills (`git-commit`,
`git-pullrequest`), so its writes match the user's own workflow. Your job
is intent + grant, not mechanics. Reading (`gh issue view`,
`gh pr view/diff`, `gh pr checks`) is always yours and always allowed.

Commits included: prompt OpenCode to commit per its `git-commit` conventions
(atomic, repo's message style); history surgery (squash, rebase, splitting)
is also OpenCode's hands — you specify the target shape, then audit with V6.

### Work from an Issue (purpose unit)

The released unit names an Issue (`Issue: #42` / a URL) — the Issue is
the spec:

1. Read it first (`gh issue view 42 --comments`): acceptance criteria,
   linked parent/sub-issues, discussion.
2. Ground the unit cycle's decompose on it — a fresh plan run, no base
   session (`references/opencode.md` <UnitCycle>).
3. Prompts tell OpenCode the Issue context: branch names reference it
   (OpenCode's conventions handle this), the PR body carries `Closes #42`
   (A2 — the merge closes the Issue; no issue-write grant needed).
4. Ambiguity inside the Issue (criteria conflict, stale spec) is a `Q<n>`
   block, same as any material decision — never silently reinterpret a
   registered requirement.

### Stacked PRs (multi-PR purpose, A2)

A purpose sized for more than one PR grows as a **native GitHub stack,
one layer at a time**: prompt OpenCode to open each layer through its
PR skill ("push this as the next layer of the stack"), never all
layers at once. After the orchestrator merges a layer it will tell you
to rebase/retarget the remaining layers — run that through OpenCode
too, then audit with V6 (no dropped commits).

### PR review response

Review comments arrived on your PR (the task body or a comment says so):

1. Read the review state first: `gh pr view <n> --comments` /
   `gh pr diff <n>` — group the comments into concerns.
2. Each concern is a normal change: fix in the current unit's build fork (or
   a fresh fork for a reopened task), verify (`references/verify.md`),
   commit, push (A2 covers pushing to your own PR branch).
3. Replies and re-request go through OpenCode (A2 covers own-PR
   maintenance): answer each thread with what changed (commit ref) or why
   not, then re-request review.
4. A review demand outside the grant (new dependency, architecture change,
   scope growth) is a `Q<n>` question in your reply — a reviewer's comment
   is input, not a grant expansion.

### Board sync

Board state is always the orchestrator's job — just report what shipped
(Issue numbers, PR link, commits) so it can close the loop.

## ReportAssembly

The core file's <Report> section is the contract; this is the assembly
discipline. A report is **evidence-backed**: every claim points at a command
you ran, a diff you read, or an artifact you attached.

- **Verification evidence is itemized** — which V-checks ran
  (`references/verify.md`), the commands + outcomes, and each intent-gate
  result (repro replay, before/after suite, baseline numbers). A skipped REQ
  check is named with its reason, never silent.
- **Remote actions map to grants** — every push/PR write named in the
  report cites the Authority line (or follow-up grant message) that
  allowed it.
- **Pointers over payloads** — branch names, PR/Issue URLs, commit shas,
  file paths. Bulky evidence (diffs, assessments, logs, outlines) lives in
  worktree files you name; the reply carries the substance. No secrets or
  raw logs.
- **Headline** — the reply/summary opens with 1-2 plain sentences a
  non-engineer can act on; the itemized evidence follows.

## Pitfalls

- Raw `gh issue create` / hand-built PR bodies — conventions live in
  OpenCode's skills; prompt intent instead.
- Auditing nothing after OpenCode's git surgery — V6 exists because history
  rewrites can drop commits silently.
- Reporting "verified" without itemized evidence — an unnamed check didn't
  happen.
- Pushing or opening a PR because the work "deserves" it — grants, not
  quality, decide remote actions.
- Merging anything, ever — `gh pr merge` is never yours at any grant.
- Writing Issues/board items at any grant — GitHub bookkeeping is the
  orchestrator's (a PR's `Closes #n` is the no-grant way to close one).

## Verification

- Every remote action in this task maps to a grant line; none exceeded it.
- The report itemizes V-checks + outcomes and carries pointers (URLs, shas,
  attachments); metadata follows the board convention.
- Issue-driven work shipped a PR with `Closes #n`; review-response work
  answered every thread with a commit ref or a reason.
