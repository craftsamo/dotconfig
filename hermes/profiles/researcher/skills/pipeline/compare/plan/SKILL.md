---
name: plan-compare
description: >-
  Compare, Plan stage: propose the closed option roster, fixed criteria and
  weights, depth per option and done criteria for one decision, and obtain
  the client's agreement. No gathering; not an open investigation, claim
  verdicts or consumer directives.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, compare, plan]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Plan>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="plan-compare")`. Reuse only full bodies in
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

# Compare: Plan

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

Bring the proposal into the kernel's Plan template and agreement reply. Label
nonblocking assumptions instead of stalling, but do not silently fix a
deliverable-defining option set. If discovering options needs external sources,
obtain agreement on a bounded preliminary Build first, then revise and agree
the matrix Plan. New criteria or options during execution need renewed scope
agreement, not a more flattering axis for one option.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
Plan into [build-compare](../build/SKILL.md), not a restart. Keep
this mode for the unit; another kind of question is another agreed unit with
its own entries, never a silent switch.
