---
name: investigate-researcher
description: >-
  Investigate an open research question: propose its scope, gather scored
  evidence under agreement, self-check and deliver an evidence pack. Not
  option comparison, claim verdicts, consumer directives or artifact
  production.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, investigate]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry,
before any stage. On every inbound turn/completion and before a midturn mode,
stage or scope change, reselect the mode and load this entry with
`skill_view(name="investigate-researcher")` and the current stage's shared reference with
`skill_view(name="researcher-pipeline", file_path="references/<stage>.md")`:
[Plan](../references/plan.md), [Build](../references/build.md) or
[QA](../references/qa.md). Reuse only full bodies in current context, never a
past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../references/gather.md). Reading strategy does not authorize searches.
Evidence from a chain also requires that chain's shared reference:
[EVM](../references/platforms/evm.md) or [Solana](../references/platforms/solana.md).
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/../references/<stage>.md`,
`${HERMES_SKILL_DIR}/../references/gather.md` and
`${HERMES_SKILL_DIR}/../references/platforms/<chain>.md` as applicable. Follow
`next_offset` through actual truncation; if recovery fails, stop the affected
action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Investigate

Use for an open question or synthesis serving a decision, not enumeration,
named-option comparison, fixed-claim verdicts or consumer directives alone.
The deliverable is an evidence pack: conclusion-led synthesis with scored sources.

## Plan

1. Translate the purpose into a proposed settled question and decision context.
   Name the sub-questions needed to answer it and the supplied source base.
   If no question is discernible, report the spec gap with candidate framings;
   do not research a guessed framing.
2. Propose done criteria: each sub-question will be closed by evidence or left
   explicitly open with what would close it. Set recency/source requirements,
   depth, exclusions, report shape and runtime budget to the decision's stakes.
3. If one question contains several distinct decisions, identify the granularity
   issue and propose ordered own-role units with boundaries for agreement.
   Do not silently absorb them into an unlimited landscape survey. Heavy breadth
   becomes a bounded retrieval dependency request to caller.
4. Name the output categories: Summary, Sources, Key Observations, Corroboration,
   Uncertainty and Implications for Caller, with per-claim confidence. Identify
   any durable artifact path and retained Review requirement.

Bring the proposal into Plan's agreement reply. Harmless assumptions may be
labeled, but missing deliverable-defining choices need agreement. Use supplied
material only; an external scoping search needs its own approved preliminary
Build. Do not take the caller's final domain decision unless explicitly asked.

## Build

Execute one agreed question with decision context and done criteria using
Build's Method and the kernel source/citation floors. An ordered plan may
contain more than one pack; finish and retain each separately within its scope.
Missing framing returns to Plan, not a guessed question or broader survey.

1. Synthesize: lead with the conclusion, then its evidence.
2. Judge: state confidence (high / med / low) per claim, list open gaps and
   implications for caller. Do not make the caller's final domain decision
   unless explicitly asked. Separate inferred implications from observations.
3. Close each agreed sub-question or state its openness and what would close
   it. An inaccessible/stale source or unresolved conflict is not confirmation.

## Output template

```markdown
## Summary
- <2-5 decision-relevant findings, confidence per claim>
## Sources
- <URL/id> - <author/publisher>, <published/observed>, <retrieved when relevant>
  Supports: <finding>; Does not prove: <limit>; Reliability: <A-F>; Credibility: <1-6>
## Key Observations
- <observation grounded in a cited source>
## Corroboration
- <supported / single-source / contradicted, per claim>
## Uncertainty
- <unknowns, inaccessible/stale sources, unresolved conflicts, what would close them>
## Implications for Caller
- <how the evidence bears on the decision without taking it over>
```

Shorten sections for compact output, but retain all categories and distinguish
inference from observation. Write requested artifacts to the durable path and
name them in the reply. Pass the actual report and evidence to QA; a polished
summary alone is not evidence that the question's done criteria were met.

## Verification

Inspect the actual pack against its agreed question, sub-questions and done
criteria. This checks Researcher's result, not caller final acceptance.

- All categories survive, even in compact output: Summary, Sources, Key
  Observations, Corroboration, Uncertainty and Implications for Caller.
- The conclusion leads and evidence follows; the summary has 2-5
  decision-relevant findings, with confidence high/med/low per claim.
- Every sub-question is closed with evidence or explicitly open with what would
  close it. Scope/granularity findings were reported, not absorbed into a survey.
- Source metadata records URL/id, author/publisher, publication/observation and
  retrieval time where relevant, both scores, supports and does-not-prove limits.
- Observations trace to sources; corroboration distinguishes independent support,
  single-source and contradiction. Inference is labeled, inaccessible/stale
  sources and unresolved conflicts remain uncertainty, and counterevidence was
  considered rather than hidden behind a confident synthesis.
- Implications inform the caller's decision without taking it over unless
  explicitly requested. Requested artifacts are at named durable paths.

Report checked, unmet and unknown conditions in QA's output. Missing evidence
is unknown, never a new self-score. A narrow omitted-category or evidence
correction goes to Build only within agreed scope and remaining budget; a new
question/depth expansion needs Plan and client agreement.

## Handoff

Plan ends at the client's agreement, Build at the Output template and QA at the
self-checked delivery; each stage's own Handoff in its shared reference says
what follows. Keep this mode for the unit; another kind of question is another
agreed unit with its own mode entry, never a silent switch.
