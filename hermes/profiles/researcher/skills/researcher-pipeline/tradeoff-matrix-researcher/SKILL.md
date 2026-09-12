---
name: tradeoff-matrix-researcher
description: >-
  Compare named options using fixed criteria and evidence. Use for one
  decision with a closed option set and fixed criteria, scored per cell
  with a confidence-rated recommendation. Not for open-ended synthesis
  (evidence-pack), claim-by-claim verification (fact-check), consumer
  directives (guidance), breadth retrieval, or artifact crafting/QA.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel and shared gather reference.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, tradeoff-matrix]
---

<ReadBeforeWork>

Before working this entry, load the current researcher-pipeline kernel's full
body (unit discipline, source evaluation, citation rules, and the card gate)
with `skill_view(name="researcher-pipeline")` — reuse only a full
current-context body, never a summary or a past load record. Direct entry
into this unit still requires the kernel body first.

Gathering beyond a few direct lookups needs the gather engine: call
`skill_view(name="researcher-pipeline", file_path="references/gather.md")` —
see [Gather](../references/gather.md).

If `skill_view` returns unchanged while a full body is missing, or cannot
return a required body, fall back to `read_file` on the
canonical paths — `${HERMES_SKILL_DIR}/../SKILL.md` for the kernel,
`${HERMES_SKILL_DIR}/../references/gather.md` for the gather engine, and
`${HERMES_SKILL_DIR}/SKILL.md` for this entry — following `next_offset` only
for actual truncation, never an artificial range or an alternate path to
dodge dedup. If the body still cannot be recovered, stop the affected
research rather than proceed without it.

A selection change is not a new grant: if the request needs a missing or
wider unit scope than what was released, return that gap to the requester
and keep the original job scope — never restart or self-expand it.

This entry does no card work: the kernel refuses every kanban card with
`kanban_block(kind=capability)` before any research begins.

</ReadBeforeWork>

# Tradeoff-matrix unit — decision support / Plan consultations

Loaded when the released unit compares named options (the assistant's
Plan consultation dispatched as a session brief, or any explicit
comparison request). The unit releases with a closed option set and fixed
criteria; the deliverable is a decision aid: options × criteria, scored
from evidence, with a recommendation — delivered fast enough to keep a
live planning loop moving.

## Rules

- **Time-boxed.** Depth per option is bounded by the decision's stakes —
  an assistant Plan mode consultation gets hours-of-work compressed into the
  task's runtime budget, not an exhaustive survey. Gaps become `Unknown` cells
  with a note, never guesses.
- **Criteria before evidence.** Fix the comparison axes first (from the
  caller's decision context; add the 2-3 they forgot — ops burden,
  reversibility, maturity); gather against them, so every option is judged
  on the same axes.
- **Assume, don't block, by default** — label assumptions; an ambiguous
  or still-growing option set is the exception: a spec-gap (or
  granularity) finding back to the assistant, never a guessed roster.

## Procedure

1. Restate the decision, the option set, and the criteria (with weights if
   the caller implied priorities).
2. Gather per the core <Method>, scoped to filling the matrix — primary
   docs and credible experience reports per option.
3. Score each cell with evidence or mark it `Unknown`; note per-option
   deal-breakers found along the way.
4. Recommend: one option (or a conditional split — "A unless X"), with the
   reasoning and its confidence.

## Output template

```markdown
## Decision
<what is being decided, for what context, one line>
## Matrix
| Criterion (weight) | Option A | Option B | … |
| --- | --- | --- | --- |
| <criterion> | <finding [source ref]> | … | … |
## Deal-breakers
- <option>: <disqualifying finding, if any, with source>
## Recommendation
<option> — <reasoning, 2-4 lines; confidence high/med/low>
## Sources
- <URL/id> — <author/publisher>, <date> · Reliability <A–F> · Credibility <1–6>
## Assumptions & unknowns
- <labeled assumptions; Unknown cells and what would resolve them>
```

## Handoff

After every option and criterion is checked, deliver the structured report
in your reply (resident session or A2A peer), and write artifacts/ledgers
to the durable path when the brief names one.

## Pitfalls

- A matrix with no recommendation — the caller asked to be helped deciding.
- Padding weak cells with plausible-sounding filler instead of `Unknown`.
- Comparing options on different axes (each option's marketing strengths)
  instead of the fixed criteria.
- Exhaustive research on one option while others get a skim.

## Verification

- Every option scored on every criterion (or explicitly `Unknown`);
  recommendation present with confidence; cells trace to scored sources.
