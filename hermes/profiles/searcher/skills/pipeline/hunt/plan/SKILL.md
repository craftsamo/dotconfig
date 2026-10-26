---
name: plan-hunt
description: >-
  Hunt, Plan stage: propose the settled question, sub-areas, done criteria,
  exclusions, hop cap and source-map output for a primary-source trail, and
  obtain the client's agreement. No retrieval; not long sweeps or verdicts.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
    tags: [search, hunt, plan]
---

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn mode, stage or
scope change, require full-body kernel and this stage entry in current context,
not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` before any stage; its `<Plan>` section
is the stage this entry specializes. Load `skill_view(name="plan-hunt")`.
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

# Hunt: Plan

Use for **exhaustive source hunts**: obscure topics, contested claims
needing primary sources, provenance chases — always against the brief's
done criteria and scope exclusions ("find everything" with neither is a
spec gap, not a hunt).
Deliverable = a structured **source map** built by following the trail from
secondary mentions to primary documents. Depth of coverage — still retrieval,
not analysis or conclusions.

## Plan

Choose hunt for obscure topics, contested claims needing primary sources or
provenance trails. Propose the settled question, sub-areas, done criteria, scope
exclusions, freshness, finite hop/time/call cap and source-map output. "Find
everything" without criteria or exclusions is a spec gap, not an execution brief.
Plan depth from secondary mentions toward primary documents, not truth judgments.

Propose a hunt as one resident conversation: hops run until saturation, the
done criteria or the agreed cap, and a turn that ends first hands back its
ledger and gaps for the caller to continue. A long sweep is still sweep.
Existing frontier and consumed budget survive a refined Plan; never grant
another full hunt merely on resume. Bring the proposal into the kernel's Plan
template and agreement reply.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
proposal into [build-hunt](../build/SKILL.md), not a restart. Keep
this mode for the unit; another kind of retrieval is another agreed unit with
its own entries, never a silent switch.
