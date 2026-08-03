# Engineer execution reference

Load when an execution shape includes Engineer work. It supplies the direct
TaskSpec and Authority rules; it does not replace RequirementSpec normalization
or either approval required by a `planned` shape.

## When direct execution fits

- The user has **already specified scope and approach in detail** — clear
  goal, known file(s)/area, no architecture decisions left open.
- Examples: "fix the off-by-one in `foo()`, the test is `bar_test.py`",
  "add field X to schema Y and the matching API endpoint we did for Z".

If architecture, scope, dependencies, migration shape, or grants remain
materially unsettled, choose `planned` and load `references/plan.md`. A clear
2-3 stage implementation may use `chain`; do not hide planning decisions inside
a direct Engineer card.

## Writing a tight Authority

For `single` or `chain`, the Authority line is the only durable record of what
the user pre-approved. For `planned`, copy it exactly from the approved
ExecutionOutline. Use the preset table in `<TaskSpec>`, explicit and minimal:

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
- `skills: ["engineer-pipeline"]` — mandatory on every engineer card: the
  dispatcher preloads it mechanically, guaranteeing the engineer's
  routing/authority kernel is in context.
- `workspace_kind: worktree` + absolute `workspace_path` (or `project:
  <slug>` for a deterministic project branch) — code work needs isolation
  and a preserved OpenCode session.
- Body: Goal / Inputs / Done criteria / Output / Constraints / Authority
  (per above).

## After dispatch

Standard `<AfterCreate>` ack, `<Failures>` recovery,
`<BlockedTriage>` for any engineer block. The dialogue loop is the safety
net — engineer blocks on questions outside the grant; within the grant,
answer autonomously and inform.
