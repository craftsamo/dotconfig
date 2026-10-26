---
name: plan-advise
description: >-
  Advise, Plan stage: name the consumer and the decision points the guidance
  must close, the evidence base, done criteria and output categories, and
  obtain the client's agreement. No gathering; not the consumer's artifact,
  an open investigation, option comparison or claim verdicts.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, advise, plan]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Plan>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="plan-advise")`. Reuse only full bodies in
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

# Advise: Plan

Use for principles, constraints, dos/don'ts and selection rules someone will
act on. The result is guidance derived from sources and/or parent-task results,
directives the agreed consumer can act on without rereading sources; it is not
production of the artifact they will make.

## Plan

1. Name the consumer and the decision points the guidance must close. Propose
   them from the client's purpose rather than demanding a prebuilt list. A missing
   consumer is a spec gap when it changes what to research; otherwise label the
   harmless assumption for agreement.
2. Identify the supplied evidence base, prior task IDs/results and examples.
   These are source inputs, not authorization for wider inquiry. Propose targeted
   evidence fills, recency needs and the depth/budget needed for this consumer.
3. Agree done criteria: each decision point closes with a traced, checkable
   directive or is explicitly left open. Plan MUST constraints, SHOULD
   recommendations and consumer-owned open choices as separate output categories;
   do not predeclare unsupported preferences as constraints.
4. State scope/exclusions, durable outputs if requested and review material.
   Lead with the two or three decisions that would most change the consumer's
   behavior, not an exhaustive list of dos/don'ts.

Bring the proposal into the kernel's Plan template and agreement reply. If
asked for both guidance and the artifact, propose the guidance within this
role and report the production mismatch to caller. Scripts/storyboards/copy,
media and code remain other roles' production, not assignments made here.
Use supplied material in Plan; get agreement before any external evidence fill.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
Plan into [build-advise](../build/SKILL.md), not a restart. Keep
this mode for the unit; another kind of question is another agreed unit with
its own entries, never a silent switch.
