---
name: plan-lookup
description: >-
  Lookup, Plan stage: propose the question or itemized batch, entities, time
  window, source classes, exclusions and query cap for specific answers, and
  obtain the client's agreement. No retrieval; not enumeration or source
  trails.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
    tags: [search, lookup, plan]
---

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn mode, stage or
scope change, require full-body kernel and this stage entry in current context,
not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` before any stage; its `<Plan>` section
is the stage this entry specializes. Load `skill_view(name="plan-lookup")`.
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

# Lookup: Plan

Use when the unit wants **specific answers**: a fact, a doc/link,
"latest on X", who-said-what, a version, a date. This is the **default mode**
when no other fits; a batch releases as one unit with an itemized question
list — answer item by item, none silently dropped. Deliverable = claims +
source URLs. Done when the question is answered with sources — not when the
web is exhausted.

## Plan

Choose lookup for specific facts, documents/links, latest events, who-said-what,
versions or dates; it is the default when neither enumeration nor a source trail
is needed. Propose one question or an itemized batch with no silently dropped
items. Set entities, time window/freshness, source classes, exclusions, finite
query cap and link-first output. Done means each question has a sourced answer
or named miss with attempts, not exhausting the web. Where stakes warrant,
include independent corroboration, leaving conflicting answers unadjudicated.
Bring the proposal into the kernel's Plan template and agreement reply.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
proposal into [build-lookup](../build/SKILL.md), not a restart. Keep
this mode for the unit; another kind of retrieval is another agreed unit with
its own entries, never a silent switch.
