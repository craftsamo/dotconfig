# Build a Tradeoff Matrix

Produce a decision aid fast enough for the agreed planning loop: closed options
by fixed criteria, sourced cells and a confidence-rated recommendation.

## Procedure

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
