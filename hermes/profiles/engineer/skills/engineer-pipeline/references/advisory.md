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
   only if you invoke OpenCode at all. If the verdict turns on what the
   executor or the machine can do here (a technique OpenCode owns, a
   subagent, a tool, credentials, secret injection), load `opencode-env` /
   `machine-env` and confirm with their recipes — an unverified capability
   claim is the one assumption you may not label and move past.
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

## Plan drafts moved to the plan slice

Producing a **draft implementation plan** (a Wave outline for an
implementation goal) is no longer an advisory variant — it is the dedicated
**plan** slice (`references/plan.md`, body opener
`Plan — outline the Waves, don't build.`). Advisory stays feasibility-only: it
judges *whether* a change is buildable and its rough shape / risk / size; plan
lays out *how*, at Wave granularity, on a repo that already exists. If a
consultation body asks for a plan draft, give the feasibility verdict inline
and note it should be dispatched as a `Plan —` task for the outline.

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
