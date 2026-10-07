---
name: compare-researcher
description: >-
  Compare named options for one decision on fixed criteria: agree the roster
  and axes, fill every cell with scored evidence or Unknown, self-check and
  recommend. Not open surveys, claim verdicts or artifact production.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, compare]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry,
before any stage. On every inbound turn/completion and before a midturn mode,
stage or scope change, reselect the mode and load this entry with
`skill_view(name="compare-researcher")` and the current stage's shared reference with
`skill_view(name="researcher-pipeline", file_path="references/<stage>.md")`:
[Plan](../references/plan.md), [Build](../references/build.md) or
[QA](../references/qa.md). Reuse only full bodies in current context, never a
past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../references/gather.md). Reading strategy does not authorize searches.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/../references/<stage>.md`
and `${HERMES_SKILL_DIR}/../references/gather.md` as applicable. Follow
`next_offset` through actual truncation; if recovery fails, stop the affected
action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Compare

Use for one decision supported by a closed option set and fixed criteria. The
deliverable is a tradeoff matrix: closed options by fixed criteria, sourced
cells and a confidence-rated recommendation, fast enough for the agreed
planning loop. This can support a live caller planning consultation without
making Researcher's own Plan stage an external research operation.

## Plan

1. Restate the decision and context. Derive a proposed option roster from
   supplied material. An ambiguous or growing roster is a spec-gap/granularity
   finding, never permission to guess or gather unlimited candidates.
2. Fix criteria before evidence: propose the axes from the decision context and
   the 2-3 relevant omissions, such as operations burden, reversibility and
   maturity. Include weights when the caller implies priorities and label those
   proposed weights for agreement. Every option must face the same axes.
3. Bound depth per option by stakes and runtime budget. A live Plan consultation
   compresses useful decision support into its budget, not an exhaustive survey.
   Propose balanced effort; unresolved cells will be `Unknown` with what would
   resolve them, never plausible filler.
4. Agree the closed roster, fixed criteria/weights, exclusions, time box, output
   and done criteria: every cell sourced or `Unknown`, deal-breakers reported,
   and a confidence-rated recommendation (possibly a conditional split).

Label nonblocking assumptions instead of stalling, but do not silently fix a
deliverable-defining option set. If discovering options needs external sources,
obtain agreement on a bounded preliminary Build first, then revise and agree
the matrix Plan. New criteria or options during execution need renewed scope
agreement, not a more flattering axis for one option.

## Build

1. Restate the agreed decision, option set and criteria, including agreed
   weights. Do not add criteria or grow the roster while gathering; return
   those changes to Plan for agreement. Label harmless assumptions.
2. Gather using Build's Method, scoped to filling the matrix: primary docs and
   credible experience reports per option. Keep depth per option bounded by
   stakes and runtime budget, not exhaustive research for a live consultation.
3. Score every cell with evidence or mark it `Unknown`; note sourced per-option
   deal-breakers. Compare all options on the same axes, not their individual
   marketing strengths. Balance effort instead of deep-reading one and skimming
   the rest. Never pad a weak cell with plausible-sounding filler.
4. Recommend one option or a conditional split ("A unless X"), with reasoning
   and confidence. Missing evidence remains `Unknown` with a resolution note,
   not a guessed score or an excuse to omit a recommendation's limitations.

## Output template

```markdown
## Decision
<what is being decided, for what context, one line>
## Matrix
| Criterion (weight) | Option A | Option B | ... |
| --- | --- | --- | --- |
| <criterion> | <finding [source ref]> | <finding or Unknown> | ... |
## Deal-breakers
- <option>: <disqualifying finding, if any, with source>
## Recommendation
<option or conditional split> - <reasoning, 2-4 lines; confidence high/med/low>
## Sources
- <URL/id> - <author/publisher>, <date>; Reliability <A-F>; Credibility <1-6>
## Assumptions & unknowns
- <labeled assumptions; Unknown cells and what would resolve them>
```

Do not return only a matrix with no recommendation: the caller asked for
decision support. If evidence cannot distinguish options, explain that as the
conditional recommendation rather than invent a winner. Write requested
artifacts to the durable path, name them and pass the full matrix to QA.

## Verification

Compare the delivered matrix with the agreed decision, closed option roster,
fixed criteria and weights. This is evidence self-check, not choosing for the
caller or grading the downstream artifact.

- Every option is evaluated on every criterion or explicitly `Unknown`; every
  filled cell traces to a scored source and does not outrun what it proves.
- Options share the same axes and agreed weights, not individually favorable
  marketing criteria. Effort was bounded and balanced, not exhaustive for one
  option and superficial for others.
- Decision/context, Matrix, Deal-breakers, Recommendation, Sources and
  Assumptions & unknowns are present. Deal-breakers are sourced, not preferences.
- A recommendation is present with reasoning and confidence high/med/low; a
  conditional split is legitimate. When evidence cannot distinguish options,
  the recommendation says so instead of inventing a winner.
- Assumptions are labeled; weak cells are not padded with plausible filler.
  Unknown cells state what would resolve them. Source metadata and both trust
  axes are present; counterevidence and recommendation limits remain visible.
- No option/criterion was silently added, dropped or changed; requested durable
  outputs are named and retain the complete matrix.

Use QA's checked/unmet/unknown report, not a new numeric quality rubric. Correct
an in-scope cell or missing explanation in Build only within remaining budget.
A growing roster, new criteria or extra investigation beyond budget returns to
Plan for agreement, preserving the original result and consumed budget.

## Handoff

Plan ends at the client's agreement, Build at the Output template and QA at the
self-checked delivery; each stage's own Handoff in its shared reference says
what follows. Keep this mode for the unit; another kind of question is another
agreed unit with its own mode entry, never a silent switch.
