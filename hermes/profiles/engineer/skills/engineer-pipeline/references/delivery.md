# Delivery — GitHub flow and the evidence-backed handoff (engine)

Load this when the work leaves the worktree: committing, pushing, PRs,
Issue/board interaction, responding to review, and assembling the final
report. Execution goes through OpenCode; **auditing the result is yours**
(`references/verify.md` V6). The core file's Authority contract decides what
is allowed at all.

## GitHubFlow

All GitHub writes go **through OpenCode**, never through your own `gh` calls —
OpenCode owns the repo's conventions via its skills (`git-commit`,
`git-pullrequest`, `manage-github-projects`) and custom `github_project_*`
tools, so its writes match the user's own workflow. Your job is intent +
grant, not mechanics. Reading (`gh issue view`, `gh pr view/diff`,
`gh pr checks`) is always yours and always allowed.

Commits included: prompt OpenCode to commit per its `git-commit` conventions
(atomic, repo's message style); history surgery (squash, rebase, splitting)
is also OpenCode's hands — you specify the target shape, then audit with V6.

### Work from an Issue

Task body names an Issue (`Issue: #42` / a URL) — the Issue is the outline:

1. Read it first (`gh issue view 42 --comments`): acceptance criteria,
   linked parent/sub-issues, discussion.
2. Treat its checklist/criteria as the Wave list; where the RiskGate needs a
   base, seed the base session from the Issue body verbatim
   (`references/opencode.md` <OpenCodeLoop>).
3. Prompts tell OpenCode the Issue context: branch names reference it
   (OpenCode's conventions handle this), the PR body carries `Closes #42`
   (A2 — the merge closes the Issue; no issue-write grant needed).
4. Ambiguity inside the Issue (criteria conflict, stale spec) is a `Q<n>`
   block, same as any material decision — never silently reinterpret a
   registered requirement.

### PR review response

Review comments arrived on your PR (the task body or a comment says so):

1. Read the review state first: `gh pr view <n> --comments` /
   `gh pr diff <n>` — group the comments into concerns.
2. Each concern is a normal change: fix in the current Wave's build fork (or
   a fresh fork for a reopened task), verify (`references/verify.md`),
   commit, push (A2 covers pushing to your own PR branch).
3. Replies and re-request go through OpenCode (A2 covers own-PR
   maintenance): answer each thread with what changed (commit ref) or why
   not, then re-request review.
4. A review demand outside the grant (new dependency, architecture change,
   scope growth) is a `Q<n>` block — a reviewer's comment is input, not an
   `AUTHORITY+` grant.

### Board sync

With `issues: write` granted, close the loop on the board after the work
ships: move the Issue's project item status, check off satisfied checklist
items, comment completion pointers — via OpenCode (its
`manage-github-projects` conventions). Without the grant, board state is the
orchestrator's job; just report what shipped.

## ReportAssembly

The core file's <Report> section is the contract; this is the assembly
discipline. A report is **evidence-backed**: every claim points at a command
you ran, a diff you read, or an artifact you attached.

- **Verification evidence is itemized** — which V-checks ran
  (`references/verify.md`), the commands + outcomes, and each intent-gate
  result (repro replay, before/after suite, baseline numbers). A skipped REQ
  check is named with its reason, never silent.
- **Remote actions map to grants** — every push/PR/Issue write named in the
  report cites the Authority line (or `AUTHORITY+:` comment) that allowed
  it.
- **Pointers over payloads** — branch names, PR/Issue URLs, commit shas,
  attachment names. Bulky evidence (diffs, assessments, logs, outlines)
  goes through `kanban_attach`; the message carries the substance.
- **Machine-readable handoff** — `kanban_complete(metadata={...})` contains
  exactly one completion envelope at `metadata.completion` with `status`,
  `summary`, and `metadata`. Put the board convention keys `changed_files`,
  `verification` (the commands run), `dependencies`, `retry_notes`, and
  `residual_risk` in that nested metadata, plus mode-specific keys such as
  `issues` or `base_session`. When an artifact is attached, also return exactly
  one `metadata.artifact_handoff` with `artifacts`, `verification`, and `qa`.
  Every artifact entry carries `name`, `sha256`, `purpose`, and this task's
  `source_task_id`.
  `metadata.completion.artifacts` and the handoff name the exact same durable
  output inventory; use an empty completion artifact list when no output file
  was attached.
  No secrets or raw logs.
- **Chat summary** — the `kanban_complete` summary is 1-2 plain sentences a
  non-engineer can act on; it is delivered verbatim to the requester's chat.

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
- Writing Issues/board items on an A-preset alone — that needs
  `issues: write` (a PR's `Closes #n` is the no-grant way to close one).

## Verification

- Every remote action in this task maps to a grant line; none exceeded it.
- The report itemizes V-checks + outcomes and carries pointers (URLs, shas,
  attachments); metadata follows the board convention.
- Issue-driven work shipped a PR with `Closes #n`; review-response work
  answered every thread with a commit ref or a reason.
