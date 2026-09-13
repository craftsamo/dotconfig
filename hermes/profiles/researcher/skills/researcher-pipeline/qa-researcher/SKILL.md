---
name: qa-researcher
description: >-
  QA research evidence against agreed scope. Use on completed research
  or corrections; report checked, unmet and unknown conditions, never caller
  final acceptance, artifact craft QA or a new self-scoring rubric.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, qa]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry,
and run its card gate before checking: refuse every kanban card with
`kanban_block(kind=capability)`. On every inbound turn/completion and before a
midturn phase, unit or scope change, reselect and load this phase and its
selected unit using `skill_view(name="qa-researcher")` and
`skill_view(name="qa-researcher", file_path="references/<unit>.md")`.
Reuse only full bodies in current context, never a past load, preload or summary.

When gathering strategy is needed beyond a few direct lookups, load
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../references/gather.md). New gathering is a Build action, not a QA
scope expansion. If `skill_view` returns unchanged with a missing body or cannot
supply it, use `read_file` on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/references/<unit>.md`
and `${HERMES_SKILL_DIR}/../references/gather.md` as applicable. Follow
`next_offset` through actual truncation; if recovery fails, stop the affected
action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

Require the agreed scope (or explicitly released settled brief) and actual Build
findings/ledger in current context, not remembered summaries. Recover missing work
products by reading their named files or retained conversation records, following
actual truncation. If the baseline or result is still unavailable, report it as
unverified and stop that check; request the missing material from the caller.
Never invent a Checked result or re-run searches merely to reconstruct lost work.

</ReadBeforeWork>

# Self-Check Research

Check the actual result and retained evidence against client-agreed scope,
done conditions and output, using the selected unit reference:
- [Evidence pack](references/evidence-pack.md): synthesis categories and question closure.
- [Tradeoff matrix](references/tradeoff-matrix.md): all cells, equal axes and justified recommendation.
- [Fact check](references/fact-check.md): exact claims, independent origins and complete ledger.
- [Guidance](references/guidance.md): traced directives and explicit open choices.

1. Reconcile agreed unit inputs with delivered findings and durable files. Check
   source inspection, reliability and credibility separately, short verbatim
   quotes, adequate metadata, counterevidence, per-claim confidence and open gaps.
   Missing evidence is unknown, not a pass or an invented source.
2. Apply the unit's Verification checks to the actual report. Use existing
   evidence floors and agreed criteria, not a newly invented rubric or numeric
   self-score. Do not take over the client's final domain decision or acceptance.
3. Report checked, unmet and unknown conditions with evidence and their effect
   on the agreed purpose. Distinguish an explicitly open research question from
   an unreported omission. Never convert this into artifact-vs-brief QA of craft,
   rendering, dimensions or delivery completeness.
4. A narrow correction can return to Build only within agreed scope and
   remaining budget; load that phase and unit before acting. New sources needed
   beyond budget, new claims, options or criteria return to Plan for agreement.
   Do not silently repair during QA or reset budget on another pass.

## Output template

```markdown
## Research Self-Check
<agreed purpose, unit(s), questions/done criteria/source policy/budget and approved changes; actual result inspected>
## Checked
<done conditions satisfied, with report/source/file evidence>
## Unmet or Unknown
<condition, evidence gap or defect, impact, what would close it>
## Budget and Disposition
<consumed/remaining; deliver, bounded Build correction or Plan agreement needed>
## Handoff
<findings summary, durable paths, review material and caller decision still pending>
```

## Verification

- Each agreed unit received its own selected QA reference check; every nontrivial
  claim traces to scored evidence, direct observation or stated uncertainty.
- Spec-gap/granularity findings remain visible; no invented evidence, self-score,
  scope expansion or artifact-quality verdict was used to manufacture completion.
- Quotes and original claims remain exact; all required durable records are
  present and named. A missing ledger remains unmet, never a chat-only pass.
- Review-required work waits for explicit go; self-check is not caller acceptance.

## Handoff

Deliver a self-contained findings reply plus self-check and named durable paths
to the resident or inbound peer caller. For `Review: required`, present exactly
the requested material and wait; revisions repeat that gate. Without it deliver
normally, leaving final acceptance with caller. After preliminary Build QA,
return to Plan to revise the main proposal. Advance another unit only if already
agreed, retaining results and consumed budget; selection never re-releases work.
