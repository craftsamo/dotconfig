---
name: plan-investigate
description: >-
  Investigate, Plan stage: turn an open research question into a proposed
  settled question, sub-questions, done criteria and budget, and obtain the
  client's agreement. No gathering; not option comparison, claim verdicts or
  consumer directives.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, investigate, plan]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Plan>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="plan-investigate")`. Reuse only full bodies in
current context, never a past load, preload or summary.

Plan uses supplied material only, so no gathering reference is needed here.
A technic the brief names or [Capabilities](../../references/capabilities.md)
matches is loaded too with `skill_view(name="<technic>")`; it adds to this
mode and never replaces it.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../../SKILL.md` and
`${HERMES_SKILL_DIR}/SKILL.md`. Follow `next_offset` through actual
truncation; if recovery fails, stop the affected action. Never evade dedup
with alternate paths or artificial ranges. Selection/resume is not a new
grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Investigate: Plan

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

Bring the proposal into the kernel's Plan template and agreement reply.
Harmless assumptions may be labeled, but missing deliverable-defining choices
need agreement. Use supplied material only; an external scoping search needs
its own approved preliminary Build. Do not take the caller's final domain
decision unless explicitly asked.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
Plan into [build-investigate](../build/SKILL.md), not a restart.
Keep this mode for the unit; another kind of question is another agreed unit
with its own entries, never a silent switch.
