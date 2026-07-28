# Research approach — reference

Loaded after Step 3 picks **Approach=Research**. Dispatches analysis work
to researcher.

## When to pick Research

- **Analysis / synthesis / comparison / evaluation / verification /
  reports** — depth work, not retrieval.
- Examples: "compare approaches A/B/C for X", "evaluate library Y against
  our constraints", "synthesize a report on topic Z from these sources",
  "check this render against the locked spec", "derive design guidance
  from these examples".

For pure retrieval (get the facts), use Search (`references/search.md`).
For mixed search→analyze→build, Plan applies (`references/plan.md`) so the
pipeline can fan-in parent results.

## Deliverable types

The researcher routes internally by deliverable — no opener needed. Write
the Done criteria to match the type; each type has an input it cannot work
without:

| Deliverable | Done criteria should fix | Must be in Inputs/Body |
| --- | --- | --- |
| Evidence-pack (default: open question, landscape, synthesis) | the question + decision context | sources/paths if known |
| Tradeoff-matrix (compare named options, recommend one) | the comparison axes (e.g. "the 4 axes we discussed") | the option set |
| Fact-check (claim verdicts) | the claims, enumerated | where each claim was made |
| Artifact-check (QA gate: deliverable vs spec, pass/fail) | the spec items that gate | the artifact (attachment/path) + the spec |
| Guidance (direction a downstream worker acts on) | who consumes it and for what decisions | parent ids / example sources |

Guidance vs writer/creator: researcher delivers the evidence-backed
direction; the crafted artifact itself (台本, copy, media) is a separate
writer/creator card that consumes it.

## Dispatching

Standard `<TaskSpec>` shape with:

- `assignee: researcher`
- `skills: ["researcher-pipeline"]` — **always** (kernel pin; add
  `web-source-vetting` / `media-artifact-verification` on top when the
  task leans on them, e.g. artifact-checks on media)
- `workspace_kind: scratch`
- Body: Goal / Inputs (links, paths, parent task ids, pasted data) /
  Done criteria (objective checks per the type table) / Output (format,
  length, language) / Constraints / Review (only when the user must sign
  off before the card closes).

Researcher's kernel runs Admiralty/SIFT source evaluation automatically —
no need to specify it in the body.

## After dispatch

Standard Step 7 mechanics. On completion, present the analysis in the
persona's voice; never paste the raw report — summarize and offer to
`kanban_show` for detail.
