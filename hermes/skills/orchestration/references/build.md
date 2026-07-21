# Build approach — reference

Loaded after Step 3 picks **Approach=Build**. Skips the Plan Loop and
dispatches implementation directly to engineer.

## When to pick Build

- The user has **already specified scope and approach in detail** — clear
  goal, known file(s)/area, no architecture decisions left open.
- Examples: "fix the off-by-one in `foo()`, the test is `bar_test.py`",
  "add field X to schema Y and the matching API endpoint we did for Z".

If there's any meaningful ambiguity in scope/approach, **default to Plan**
(`references/plan.md`) — Build is the exception, not the default, for
implementation work.

## Writing a tight Authority

Because Plan was skipped, the Authority grant in the task body is the only
place the engineer learns what's pre-approved. Use the preset table in
`<TaskSpec>`, explicit and minimal:

- **`A1`** (commit only) is the default — stay there unless the user has
  already said otherwise in chat.
- **`A2`** (+ feature-branch push / PR) — only if the user asked for a PR
  or push.
- **`A3`** (+ dependency changes) — rare from Build; if deps are in play,
  that's usually a Plan question.
- **Scope boundary overrides** — name the files/areas that are in scope,
  and explicitly call out anything nearby that is **not** to be touched
  (`scope:` / `do not touch:` lines).

Anything not granted forces the engineer into a block round-trip
(`<BlockedTriage>`), so grant what the user has sanctioned and no more.
Mid-task expansions go through `AUTHORITY+:` comments, never body edits.

## Dispatching

Standard `<TaskSpec>` shape with:

- `assignee: engineer`
- `workspace_kind: worktree` + absolute `workspace_path` (or `project:
  <slug>` for a deterministic project branch) — code work needs isolation
  and a preserved OpenCode session.
- Body: Goal / Inputs / Done criteria / Output / Constraints / Authority
  (per above).

## After dispatch

Standard Step 7 mechanics: `<AfterCreate>` ack, `<Failures>` recovery,
`<BlockedTriage>` for any engineer block. The dialogue loop is the safety
net — engineer blocks on questions outside the grant; within the grant,
answer autonomously and inform.
