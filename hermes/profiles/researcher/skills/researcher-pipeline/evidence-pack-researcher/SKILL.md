---
name: evidence-pack-researcher
description: >-
  Synthesize a settled question using scored evidence. Use for one
  settled question with done criteria, synthesized into sourced
  observations, corroboration, and confidence-rated conclusions. Not for
  breadth retrieval/surveys, named-option comparisons (tradeoff-matrix),
  fixed-claim verdicts (fact-check), consumer-facing directives (guidance),
  or artifact QA/crafting.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel and shared gather reference.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, evidence-pack]
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

# Evidence-pack unit — deep synthesis (default)

The default research unit: one settled question answered with verifiable
evidence, released with its decision context and done criteria. The core
<Method>, <SourceEvaluation>, and <CitationRules> govern the gathering
(route and delegation per [Gather](../references/gather.md)); this reference sets
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

After the evidence and open gaps pass verification, deliver the structured
report in your reply (resident session or A2A peer), and write
artifacts/ledgers to the durable path when the brief names one.

## Verification

- All categories present (Summary / Sources / Observations / Corroboration /
  Uncertainty / Implications); confidence stated per claim.
- The conclusion leads; the evidence follows; the caller's decision is
  informed, not taken over.
