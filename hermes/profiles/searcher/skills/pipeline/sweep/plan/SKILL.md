---
name: plan-sweep
description: >-
  Sweep, Plan stage: propose the population, coverage axes, floor count,
  per-item fields, exclusions and effort cap for an enumeration or a measured
  public-web observation, and obtain the client's agreement. No retrieval; not
  specific answers, source trails or rankings.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
    tags: [search, sweep, plan]
---

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn mode, stage or
scope change, require full-body kernel and this stage entry in current context,
not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` before any stage; its `<Plan>` section
is the stage this entry specializes. Load `skill_view(name="plan-sweep")`.
Plan uses supplied material only, so no service reference is read here. A
technic the brief names or [Capabilities](../../references/capabilities.md)
matches is loaded too with `skill_view(name="<technic>")`; it adds to this
mode and never replaces it.
If unchanged is returned while the earlier body is unavailable, or a body is
missing, use read_file on canonical `${HERMES_SKILL_DIR}/../../SKILL.md` and
`${HERMES_SKILL_DIR}/SKILL.md`. Follow next_offset through actual truncation;
stop the affected action if unavailable. Never evade dedup with alternate
paths or artificial ranges. Raw skill_dir is this entry's directory. Loading
does not restart coverage or the frontier, reset a budget or replay work.
Expansion needs the caller's release; selection is not a new grant.

</ReadBeforeWork>

# Sweep: Plan

Use when the unit wants **"collect / enumerate / survey as many
as possible"**: candidates, examples, instances — or a measured observation
of public web state ("how exposed is X", "how many results for Y").
Deliverable = a deduped list **plus an explicit coverage statement** (what
was searched, what was not). The brief's coverage claim carries a floor
count — treat it as a floor, not a target to stop at exactly.

## Plan

Choose sweep for collect/enumerate/survey requests, candidates/examples/instances
or measured public-web state. Propose the population and coverage axes (platform,
category, time window), floor count, fixed per-item evidence fields, exclusions,
freshness, finite effort cap and deduped list plus explicit coverage statement.
The floor is a minimum, not an exact stopping target: done is floor + saturation
or budget with shortfalls named. Separate populations into ordered same-role
units if useful, with agreement, rather than guessing expanded coverage.

For measurement, settle the observed population, engine/query/time/page-depth
method and fields to record. Counts are observations, never true totals; retain
truncation, personalization, estimates and engine-specific caveats. No risk verdict.
Bring the proposal into the kernel's Plan template and agreement reply.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
proposal into [build-sweep](../build/SKILL.md), not a restart. Keep
this mode for the unit; another kind of retrieval is another agreed unit with
its own entries, never a silent switch.
