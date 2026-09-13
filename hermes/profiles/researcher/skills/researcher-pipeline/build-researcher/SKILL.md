---
name: build-researcher
description: >-
  Build agreed depth research with scored sources. Use after client agreement
  or an explicitly authorized settled brief, not for unapproved discovery,
  scope expansion, artifact production or caller acceptance.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, build]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry,
and run its card gate before execution: refuse every kanban card with
`kanban_block(kind=capability)`. On every inbound turn/completion and before a
midturn phase, unit or scope change, reselect and load this phase and its
selected unit using `skill_view(name="build-researcher")` and
`skill_view(name="build-researcher", file_path="references/<unit>.md")`.
Reuse only full bodies in current context, never a past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../references/gather.md). If `skill_view` returns unchanged with a
missing body or cannot supply it, use `read_file` on canonical
`${HERMES_SKILL_DIR}/../SKILL.md`, `${HERMES_SKILL_DIR}/SKILL.md`,
`${HERMES_SKILL_DIR}/references/<unit>.md` and
`${HERMES_SKILL_DIR}/../references/gather.md` as applicable. Follow
`next_offset` through actual truncation; if recovery fails, stop the affected
action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Build Research

Execute only client-agreed research or an explicitly authorized settled brief.
Fields and transport kind alone are not authorization. Retain scope, exact
claims, agreed unit order, completed results and consumed/remaining budget.
Return unclear authorization or expansion to Plan; do not release it yourself.
For each current unit, read its execution and output reference:
- [Evidence pack](references/evidence-pack.md): conclusion-led synthesis.
- [Tradeoff matrix](references/tradeoff-matrix.md): equal axes, sourced cells and recommendation.
- [Fact check](references/fact-check.md): byte-for-byte originals and durable verdict ledger.
- [Guidance](references/guidance.md): traced, checkable consumer directives.

<Method>

1. **Scope.** Restate the agreed question, caller decision context, success
   criteria and sub-questions. Label harmless assumptions only when they do
   not change search strategy. Missing deliverable-defining decisions return
   as spec-gap findings; new questions/options/criteria require Plan agreement.
2. **Gather depth** per the parent Gather reference within remaining budget.
   Record for each candidate source URL/id, author/publisher, publication time,
   retrieval time when recency matters, reliability A-F, what it supports and
   what it does not prove. Searcher QA-passed parts establish coverage, not
   trust; source scoring remains Researcher's. Use file/web/vision/video,
   with no terminal/code tools; `delegate_task` covers quick parallel in-turn
   lookups only. Request heavy breadth from the caller, never a new peer.
3. **Extract directly, not from memory.** Fetch/read the source using available
   web extraction, file or permitted inspection tools. Do not rely on remembered
   summaries when the source is fetchable; snippets are not source text.
4. **Deep-read** highest-trust sources. Quote exactly and briefly only when
   wording matters; otherwise summarize and label it as a summary.
5. **Cross-reference/triangulate.** Compare independent sources, weight by trust,
   and label single-source claims. Reposts sharing one origin are not independent.
6. **Seek counterevidence.** Actively seek material that contradicts or weakens
   the conclusion rather than stopping at confirming sources.
7. **Separate categories:** Observation (direct source statement), Corroboration
   (independent support/single-source/contradicted), Inference (what follows) and
   Uncertainty (unknown, stale or weakly supported). Apply both kernel trust axes.

Synthesize using the selected unit format. Missing evidence stays unknown;
budget exhaustion is not permission to guess, delete claims or expand scope.
Stop a preliminary discovery Build at its own boundary, not at main-task completion.

</Method>

## Output template

Use the selected reference's full Output template, keeping its categories even
for compact reports. Lead with conclusions supported by evidence, per-claim
confidence and open gaps. Append scope/unit completed, sources inspected,
consumed/remaining budget, unmet done conditions, and every produced durable
path. For QA-consuming fact-checks, write the complete claim ledger, default
`claim-ledger.md`, not only a summary or a chat-only substitute.

## Verification

- Explicit authorization covers this unit, evidence gathering and remaining
  budget; no scope expansion, completed-work replay or new grant was inferred.
- The selected reference's execution and Output template were used; source
  metadata, scores, observations, inference, counterevidence and unknowns survive.
- Requested files exist at the durable path and are named in the reply;
  unresolved blockers are not presented as completed findings.

## Handoff

Load `qa-researcher` and the matching QA unit reference before reporting the
research as self-checked. Preserve exact claims, sources, output paths and
budget across that transition. QA may return a narrow correction within this
scope and remaining budget; expansion needs Plan and agreement. Neither Build
completion nor QA waives `Review: required` or supplies caller final acceptance.
