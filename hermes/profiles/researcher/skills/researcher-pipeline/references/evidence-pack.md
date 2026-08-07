# Evidence-pack unit — deep synthesis (default)

The default research unit: one settled question answered with verifiable
evidence, released with its decision context and done criteria. The core
<Method>, <SourceEvaluation>, and <CitationRules> govern the gathering
(route and delegation per `references/gather.md`); this reference sets
synthesis and output. A brief with no discernible question is a spec-gap
finding; a question that is several questions is a granularity finding —
report, don't absorb.

## Synthesis

1. **Synthesize** — lead with the conclusion, then the evidence behind it.
2. **Judge** — state confidence (high / med / low) per claim, list open
   gaps, and return implications for the caller. Don't make the caller's
   final domain decision unless explicitly asked.

## Output template

```markdown
## Summary
- 2–5 decision-relevant findings.
## Sources
- <URL/id> — <author/publisher>, <published/observed>, <retrieved?>
  - Supports: <…>   Does not prove: <…>   Reliability: <A–F> · Credibility: <1–6>
## Key Observations
- <observation grounded in a cited source>
## Corroboration
- <supported / single-source / contradicted, per claim>
## Uncertainty
- <unknowns, inaccessible/stale sources, unresolved conflicts>
## Implications for Caller
- <how the evidence bears on the decision — without taking it over>
```

Shorten sections for compact output, but keep the categories.

## Handoff

After the evidence and open gaps pass verification, deliver according to the
runtime:

- **Session runtime (default):** deliver the structured report in your reply,
  and write artifacts/ledgers to the durable path when the brief names one.
- **Card runtime:** deliver the full report in the final message, add a 1–2
  sentence completion summary, and attach artifact files.

## Verification

- All categories present (Summary / Sources / Observations / Corroboration /
  Uncertainty / Implications); confidence stated per claim.
- The conclusion leads; the evidence follows; the caller's decision is
  informed, not taken over.
