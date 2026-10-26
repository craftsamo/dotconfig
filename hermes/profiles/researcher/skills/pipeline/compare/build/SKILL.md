---
name: build-compare
description: >-
  Compare, Build stage: fill the agreed tradeoff matrix with sourced cells,
  recommend with confidence, self-check and deliver it. Requires the client's
  agreement from Plan; not an open investigation, claim verdicts or consumer
  directives.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, compare, build]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Build>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="build-compare")`. Reuse only full bodies in
current context, never a past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../../references/gather.md). Reading strategy does not authorize searches.
Evidence from a chain or from Hyperliquid also requires its shared reference:
[EVM](../../references/platforms/evm.md), [Solana](../../references/platforms/solana.md) or
[Hyperliquid](../../references/platforms/hyperliquid.md).
A technic the brief names or [Capabilities](../../references/capabilities.md)
matches is loaded too with `skill_view(name="<technic>")`; it adds to this mode
and never replaces it.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/../../references/gather.md`
and `${HERMES_SKILL_DIR}/../../references/platforms/<chain>.md` as applicable.
Follow `next_offset` through actual truncation; if recovery fails, stop the
affected action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Compare: Build

Use for one decision supported by a closed option set and fixed criteria. The
deliverable is a tradeoff matrix: closed options by fixed criteria, sourced
cells and a confidence-rated recommendation, fast enough for the agreed
planning loop.

## Build

1. Restate the agreed decision, option set and criteria, including agreed
   weights. Do not add criteria or grow the roster while gathering; return
   those changes to Plan for agreement. Label harmless assumptions.
2. Gather using the kernel's Build Method, scoped to filling the matrix:
   primary docs and credible experience reports per option. Keep depth per
   option bounded by stakes and runtime budget, not exhaustive research for a
   live consultation.
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
artifacts to the durable path, name them and check the full matrix against Verification below.

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

Put unmet or unknown conditions in Assumptions & unknowns; no new numeric quality rubric. Correct
an in-scope cell or missing explanation in Build only within remaining budget.
A growing roster, new criteria or extra investigation beyond budget returns to
[plan-compare](../plan/SKILL.md) for agreement, preserving the
original result and consumed budget.

## Handoff

Build ends, in the same turn, with the self-check against this entry's
Verification, and the reply carries what it found unmet or unknown; the
kernel's Build section says how the findings are delivered. Keep this mode for
the unit; another kind of question is another agreed unit with its own
entries, never a silent switch.
