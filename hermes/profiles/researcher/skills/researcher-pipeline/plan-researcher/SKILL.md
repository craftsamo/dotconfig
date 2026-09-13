---
name: plan-researcher
description: >-
  Plan research purpose and obtain scope agreement. Use for new or revised
  depth inquiries; propose questions and ordered research units, not external
  gathering, artifact production or final acceptance.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, plan]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry,
and run its card gate before planning: every kanban card is refused with
`kanban_block(kind=capability)`. On every inbound turn/completion and before a
midturn phase, unit or scope change, reselect and load this phase and its
selected unit using `skill_view(name="plan-researcher")` and
`skill_view(name="plan-researcher", file_path="references/<unit>.md")`.
Reuse only full bodies in current context, never a past load, preload or summary.

For gathering strategy beyond a few direct lookups, load
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../references/gather.md). Reading strategy does not authorize searches.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/references/<unit>.md`
and `${HERMES_SKILL_DIR}/../references/gather.md` as applicable. Follow
`next_offset` through actual truncation; if recovery fails, stop the affected
action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Plan Research

Use purpose, consumer, constraints, budget and supplied material to propose
research, rather than require the client to pre-decompose it. Read the selected
reference before making its choices; for a sequence, read each unit's Plan
reference before proposing that unit:
- [Evidence pack](references/evidence-pack.md): question, sub-questions and closure.
- [Tradeoff matrix](references/tradeoff-matrix.md): decision, roster and fixed axes.
- [Fact check](references/fact-check.md): exact claims, source requirements and ledger.
- [Guidance](references/guidance.md): consumer decisions and evidence base.

1. Retain the initial purpose and existing agreement. Distinguish supplied facts,
   suggested choices and open decisions. Label harmless assumptions when they
   do not change search strategy; ask one batched question round for premises
   that decide the work. Propose options and a recommendation, not a blank form.
2. Define the research scope and exclusions, questions/options/criteria/exact
   claims as applicable, done conditions, output/durable path and finite budget
   (time, calls or other caller cap). Match depth to stakes. Propose an ordered
   sequence of evidence-pack, tradeoff-matrix, fact-check and/or guidance units
   when useful, with dependencies and stop points. Never plan production work
   or assign other roles. Heavy breadth becomes a dependency request to caller.
3. Use supplied materials only. If missing options need external discovery,
   propose a bounded preliminary Build with explicit output, scope, budget and
   stop condition; wait for agreement before gathering, then return to revise
   this Plan using its self-checked result. Do not silently release the main work.
4. Present the proposed research and request agreement. Filled fields or a
   transport `kind` do not authorize execution; no self-release. Agent clients
   may agree within their existing grant without a fresh human approval for each
   ordinary lookup. Human-only permissions stay separately gated.

## Output template

```markdown
## Purpose and Consumer
<decision/use, constraints, supplied evidence and labeled assumptions>
## Proposed Research
<questions, options and criteria, exact claims or consumer decisions>
## Scope and Exclusions
<included research and explicit boundaries/dependencies>
## Ordered Units
<unit sequence, inputs/dependencies, output and done condition per unit>
## Budget and Stop Conditions
<proposed cap, already consumed, remaining, any preliminary Build boundary>
## Output and Review
<report shape, durable paths, claim ledger if needed, retained Review gate>
## Agreement Needed
<specific proposal to approve; batched Q1:/Q2: options and recommendation if blocked>
```

## Verification

- Purpose, consumer, constraints and budget inform a bounded proposal; no
  deliverable-defining choice was guessed or required from a prebuilt client plan.
- Selected unit Plan references were read; sequence stays within Researcher's
  role and includes done/output/exclusions. No unapproved external search occurred.
- Existing outputs, grant and consumed budget remain intact; unresolved spec-gap
  or granularity findings are visible. No invented agreement or human permission.

## Handoff

Wait for client agreement, then load `build-researcher` and the selected Build
unit reference. A short approval advances this retained Plan, not a restart.
An already explicitly authorized settled execution brief may go directly to
Build without ceremonial replanning. If authorization is unclear, pause that
action and ask. A planning reply is not a researched conclusion.
