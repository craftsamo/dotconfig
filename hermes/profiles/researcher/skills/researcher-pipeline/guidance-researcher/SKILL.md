---
name: guidance-researcher
description: >-
  Derive evidence-backed guidance for a named consumer. Use for a named
  consumer's decision points converted into checkable MUST/SHOULD
  directives traced to evidence. Not for open synthesis (evidence-pack),
  option comparisons (tradeoff-matrix), claim verdicts (fact-check),
  breadth retrieval, or crafting the artifact itself.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel and shared gather reference.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, guidance]
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

# Guidance unit — evidence-backed direction for a downstream worker

Loaded when the released unit is direction someone else will act on:
design principles, constraints, dos/don'ts, selection rules — derived from
evidence (sources and/or parent-task results), not the crafted artifact
itself. The unit releases with the consumer, their decision points, and
the evidence base. The core <Method> applies; the extra discipline is
converting findings into directives a consumer can execute without
rereading the sources.

Boundary: if the caller wants the artifact itself, that is another worker's
unit — 台本 / 絵コンテ / copy → writer, media → creator, code → engineer.
This unit produces the guidance such work consumes. Asked for both, deliver
the guidance and report the mismatch; don't craft.

## Procedure

1. **Name the consumer and their decision points.** Who acts on this, and
   which choices must the guidance close? A missing consumer is a
   spec-gap finding when it changes what to research; otherwise a labeled
   assumption.
2. **Gather** per the core <Method>. Inputs are often prior results the
   brief already supplies (parent task ids or their output) — treat those
   as source inputs, not new authorization for wider scope — plus targeted
   fills; guidance derived from examples cites the examples like any other
   source.
3. **Convert findings into directives.** Each directive traces to evidence.
   Separate MUST (constraints the evidence strongly supports) from SHOULD
   (recommendations with reasoning) from open choices (deliberately left
   to the consumer).
4. **Make it checkable.** Concrete parameters over adjectives — "hook
   within 2s" not "start strong"; a directive the consumer can't test
   isn't guidance yet.

## Output template

```markdown
## For
<consumer + what they will do with this, one line>
## Constraints (MUST)
- <directive> — <evidence [Reliability · Credibility]>
## Recommendations (SHOULD)
- <directive> — <evidence + reasoning; confidence high/med/low>
## Open choices
- <left to the consumer, with options where useful>
## Evidence base
- <URL/id or parent task id> — <what it contributed> · Reliability <A–F> · Credibility <1–6>
## Uncertainty
- <weakly supported directives, gaps, what would firm them up>
```

## Handoff

After the directives pass verification, deliver the structured report in
your reply (resident session or A2A peer), and write artifacts/ledgers to
the durable path when the brief names one.

## Pitfalls

- Crafting the artifact instead of the guidance — scope creep into
  writer/creator territory.
- Directives with no evidence trace — taste presented as finding.
- Adjective guidance ("make it punchy") instead of checkable parameters.
- Burying the two or three decisions that matter under exhaustive
  dos/don'ts — lead with what changes the consumer's behavior most.

## Verification

- Consumer named; every MUST/SHOULD traces to scored evidence or a parent
  result; open choices are explicit, not silently decided.
- A stranger could act on the directives without reading the sources.
