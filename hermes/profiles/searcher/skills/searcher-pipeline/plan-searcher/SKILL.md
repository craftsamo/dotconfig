---
name: plan-searcher
description: >-
  Plan: propose purpose-led retrieval scope and agreement for lookup, sweep or
  hunt. Use for new or changed search purposes, not unapproved external search.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: searcher-pipeline
    tags: [search, plan]
---

<ReadBeforeWork>

On every caller, judge, resume or completion turn and before a midturn phase,
unit or scope change, require full-body kernel, selected entry and selected unit
references in current context, not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` and its card gate before planning: a valid
card bypasses Plan for Build -> QA -> terminal; malformed cards immediately use
`kanban_block(kind=capability)`, never a plan on the card.
Load `skill_view(name="plan-searcher")` and
`skill_view(name="plan-searcher", file_path="references/<unit>.md")` for every
proposed unit. If unchanged is returned while the earlier body is unavailable,
or any body is missing, use read_file on canonical
`${HERMES_SKILL_DIR}/../SKILL.md`, `${HERMES_SKILL_DIR}/SKILL.md` and
`${HERMES_SKILL_DIR}/references/<unit>.md`. Follow next_offset through actual
truncation; stop the affected action if unavailable. Never evade dedup with
alternate paths or artificial ranges. Raw skill_dir is this entry's directory.
Loading does not restart coverage or the frontier, reset a budget or replay work.
Expansion requires the caller's release; selection is not a new grant.

</ReadBeforeWork>

# Plan Search

Read the selected unit choices before proposing it, including each unit in a
sequence: [Lookup](references/lookup.md), [Sweep](references/sweep.md),
[Hunt](references/hunt.md).

1. Start with client purpose, consumer, constraints, budget and supplied material.
   Propose the question, population/coverage, per-item fields, exclusions,
   freshness, done conditions and output, rather than demand a prebuilt plan.
   An unusable purpose needs one batched Q1:/Q2: round with options and a
   recommendation. Label harmless assumptions; do not guess defining decisions.
2. Propose a finite effort cap (time, calls or hops), preserving consumed and
   remaining budget. If needed propose ordered SAME-role units with dependencies
   and stop points, not whole project decomposition or cross-role assignment.
3. Use supplied materials only, no unapproved external search. If scope needs
   discovery, propose a bounded preliminary Build with scope, output, finite cap
   and stop condition. Obtain agreement, run Build + QA, then refine Plan and
   agree the main work; preliminary approval never releases the main search.
4. Obtain client agreement before Build. Fields or transport kind are not release.
   An explicitly authorized settled execution brief can enter Build directly;
   ordinary one-shot inquiry needs no ceremonial approval. If authorization is
   unclear, ask before that action. Agent clients may agree within their grant;
   this never substitutes for separately required human permission.

## Output template

```text
Purpose / consumer: <use and constraints; supplied material; assumptions>
Proposed search: <question, population, coverage, per-item fields, freshness>
Scope / exclusions: <boundaries and unresolved spec-gap/granularity findings>
Ordered units: <lookup/sweep/hunt, dependencies, output and done per unit>
Budget: <finite cap, consumed, remaining; preliminary Build if needed>
Delivery: <report shape and durable path if supplied>
Agreement needed: <specific proposal; Q1:/Q2: options and recommendation>
```

## Verification

Purpose and consumer determine a bounded proposal. All proposed unit Plan refs
were read; no unapproved search, guessed agreement or budget reset occurred.
Unit ordering stays retrieval-only, with scope, exclusions, done and output.

## Handoff

Wait for agreement, then load `build-searcher` and its selected unit reference.
A short approval advances this retained proposal, not a restarted Plan.
Planning is not retrieved findings or caller final acceptance.
