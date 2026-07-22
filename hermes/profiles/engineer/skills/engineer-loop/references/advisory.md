# Advisory mode — Plan-Loop feasibility consultations

Loaded when <ModeRouting> detects an advisory task (body opens with
`Advisory — inform the plan, don't ship.`, or a question-only body). The
orchestrator is mid-Plan-Loop with the user: it needs facts to make the plan
concrete, fast. Contract on the dispatch side (orchestration
`references/plan.md`): scratch workspace, small `max_runtime_seconds`
(~600), deliverable = a short assessment at the **feasibility altitude** —
"is this buildable, what's the shape, what's the risk, rough size" — not
implementation altitude.

## Rules

- **Read-only.** No commits, no code, no prototypes, no dependency installs,
  no file edits outside throwaway notes. The Authority line (if any) never
  authorizes shipping from an advisory task.
- **Time-boxed.** Answer from inspection — reading the repo, docs, history —
  not from building. If the question genuinely cannot be answered without
  building something, that IS the answer ("needs a spike task").
- **Assume, don't block, by default.** The orchestrator is waiting inside a
  live Plan Loop; a block round-trip costs more than a labeled assumption.
  Block (per core <CheckpointThenBlock>) only when every plausible reading
  of the question leads to a different verdict.

## Procedure

1. Parse the consultation: what decision is the plan waiting on? Restate it
   in one line at the top of the assessment.
2. Inspect: read the relevant repo/worktree, docs, history with your own
   tools. For heavier recon, read-only OpenCode primaries are fine — plain
   `--auto`, no permission env (`opencode run --auto --agent plan …` /
   `--agent explore …`); pick the model per `references/model-routing.md`
   only if you invoke OpenCode at all.
3. Write the assessment (format below), attach it if long
   (`kanban_attach`), deliver the substance in the final message.

## Assessment format

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<buildable / buildable-with-caveats / not-as-stated — one line>
## Shape
<how it would be built: components touched, integration points, 3-6 lines>
## Risks
<what could sink or reshape it, with where in the code the risk lives>
## Rough size
<PR-sized-unit count estimate, e.g. "2-3 units: foundation, feature, tests">
## Assumptions
<what you assumed instead of asking, labeled>
```

## Plan-draft variant

When the consultation body asks for a **draft implementation plan** (e.g.
"実装計画の草案を" / "draft the implementation plan"), the deliverable is a
plan document, not just a verdict — typically feeding a Board Plan
synthesis card (orchestration `references/plan.md`):

- Still read-only: the plan is prose; nothing is scaffolded or committed.
- Produce it with an OpenCode plan primary (`opencode run --auto --agent
  plan …`, model per `references/model-routing.md`) grounded in the actual
  repo — or from direct inspection when the repo is small or absent (new
  project: propose the stack and structure yourself).
- Then **self-assess the draft**: apply the Risks lens above to your own
  plan (what's uncertain, where it could be wrong, what a reviewer should
  challenge).
- Deliverable = the draft plan (attach if long) + the self-assessment +
  a unit split estimate. `kanban_complete` summary must name the
  attachment and carry the plan's one-line shape, since downstream cards
  see only the summary/metadata; put the unit list in
  `metadata` (e.g. {"units": [...], "stack": "..."}).

## Report

- Final message = the assessment (or its summary + attachment reference).
- `kanban_complete` summary = 1-2 plain sentences carrying the verdict —
  it is delivered verbatim to the requester's chat.

## Pitfalls

- Drifting to implementation altitude — designing the whole solution or
  writing sample code instead of assessing.
- Burning the time box on OpenCode runs when direct file reads answer it.
- Blocking on detail an assumption would cover — label and proceed.
- An unlabeled assumption load-bearing under the verdict.

## Verification

- Deliverable follows the format: verdict + shape + risks + size, question
  restated, assumptions labeled.
- Nothing was committed, edited, or installed; no code shipped.
- Runtime stayed inside the consultation's time box.
