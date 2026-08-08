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

After every option and criterion is checked, deliver according to the runtime:

- **Session runtime (default):** deliver the structured report in your reply,
  and write artifacts/ledgers to the durable path when the brief names one.
- **Card runtime:** deliver the full report in the final message, add a 1–2
  sentence completion summary, and attach artifact files.

## Pitfalls

- A matrix with no recommendation — the caller asked to be helped deciding.
- Padding weak cells with plausible-sounding filler instead of `Unknown`.
- Comparing options on different axes (each option's marketing strengths)
  instead of the fixed criteria.
- Exhaustive research on one option while others get a skim.

## Verification

- Every option scored on every criterion (or explicitly `Unknown`);
  recommendation present with confidence; cells trace to scored sources.
