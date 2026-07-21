# Research approach — reference

Loaded after Step 3 picks **Approach=Research**. Dispatches analysis work
to researcher.

## When to pick Research

- **Analysis / synthesis / comparison / evaluation / reports** — depth
  work, not retrieval.
- Examples: "compare approaches A/B/C for X", "evaluate library Y against
  our constraints", "synthesize a report on topic Z from these sources".

For pure retrieval (get the facts), use Search (`references/search.md`).
For mixed search→analyze→build, Plan applies (`references/plan.md`) so the
pipeline can fan-in parent results.

## Dispatching

Standard `<TaskSpec>` shape with:

- `assignee: researcher`
- `workspace_kind: scratch`
- Body: Goal / Inputs (links, paths, parent task ids, pasted data) /
  Done criteria (objective checks — e.g. "tradeoff matrix covering the 4
  axes we discussed, each option rated with citations") / Output (format,
  length, language) / Constraints.

Researcher's profile skill `research-pipeline` runs Admiralty/SIFT source
evaluation automatically — no need to specify it in the body.

## After dispatch

Standard Step 7 mechanics. On completion, present the analysis in the
persona's voice; never paste the raw report — summarize and offer to
`kanban_show` for detail.
