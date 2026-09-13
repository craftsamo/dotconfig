---
name: build-searcher
description: >-
  Build: retrieve agreed lookup, sweep or hunt findings with links and coverage.
  Use for released execution or valid cards, not planning or truth adjudication.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: searcher-pipeline
    tags: [search, build]
---

<ReadBeforeWork>

On every caller, judge, resume or completion turn and before a midturn phase,
unit or scope change, require full-body kernel, selected entry and selected unit
references in current context, not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` and its card gate before retrieval: valid
cards are already released for Build -> QA -> terminal without Plan negotiation;
malformed cards immediately use `kanban_block(kind=capability)`.
Load `skill_view(name="build-searcher")` and
`skill_view(name="build-searcher", file_path="references/<unit>.md")`.
If unchanged is returned while the earlier body is unavailable, or a body is
missing, use read_file on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md` and `${HERMES_SKILL_DIR}/references/<unit>.md`.
Follow next_offset through actual truncation; stop the affected action if
unavailable. Never evade dedup with alternate paths or artificial ranges.
Raw skill_dir is this entry's directory. Loading does not restart coverage or
the frontier, reset a budget or replay work. Expansion needs the caller's release;
selection is not a new grant.

</ReadBeforeWork>

# Build Search

Read the method and output of the current unit before retrieving:
[Lookup](references/lookup.md), [Sweep](references/sweep.md),
[Hunt](references/hunt.md). Read each new unit reference when switching.

1. Retain purpose, agreed scope, exclusions, done criteria, output and finite
   effort cap. Require agreement or an explicitly authorized settled execution
   brief; ordinary one-shot inquiry needs no ceremonial approval. Filled fields
    or transport kind alone are not release. Unapproved work returns to Plan.
   For ambiguity that does not change the agreed question, coverage, exclusions
   or output, assume rather than stall: state `Interpreted as: ...` as the first
   line of findings and proceed. This applies to valid cards and direct settled
   briefs too. Never guess a deliverable-defining decision or authorization.
2. Execute the selected method with primary/official sources first, real URLs
   and dates. Preserve coverage matrix, query families, frontier/hop ledger,
   consumed and remaining budget across turns. Do not replay completed work.
3. Corrections affect named findings only, within the same scope and remaining
   budget. Expansion or deliverable-defining spec gaps return to Plan and client
   agreement, or the kernel's card protocol. Do not silently stretch the unit.
4. Stop at the agreed condition, saturation or effort cap as the unit prescribes;
   report shortfalls honestly. Preliminary Build stops at its own boundary.

## Output template

Use the selected unit's full output template, adding purpose/scope, consumed and
remaining budget, retained coverage/frontier and a stop reason. Findings remain
link-first claims + URLs + dates/flags, with `Open for researcher`, not essays.
Put the interpretation line first whenever a harmless assumption was needed.

## Verification

The released unit reference was followed, its ledger retained, and the cap not
expanded. No guessed URL, silent gap, new grant or synthesis entered the result.
Load QA before declaring delivery checked; Build is not independent acceptance.

## Handoff

Load `qa-searcher` and its matching unit reference with the agreed brief, full
findings and ledger. Goal-mode ongoing hops preserve state for the next judge
turn; terminal delivery follows QA. A preliminary result goes through QA to
refined Plan, never directly into an unapproved main search.
