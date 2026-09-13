---
name: qa-searcher
description: >-
  QA: check retrieval results against agreed scope, coverage and links. Use after
  lookup, sweep or hunt, not trust verdicts, synthesis or caller acceptance.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: searcher-pipeline
    tags: [search, qa]
---

<ReadBeforeWork>

On every caller, judge, resume or completion turn and before a midturn phase,
unit or scope change, require full-body kernel, selected entry and selected unit
references in current context, not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` and its card gate before checking: a valid
card stays on Build -> QA -> terminal without new Plan negotiation; a malformed
card immediately uses `kanban_block(kind=capability)`, not planning on the card.
Load `skill_view(name="qa-searcher")` and
`skill_view(name="qa-searcher", file_path="references/<unit>.md")`.
If unchanged is returned while the earlier body is unavailable, or a body is
missing, use read_file on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md` and `${HERMES_SKILL_DIR}/references/<unit>.md`.
Follow next_offset through actual truncation; stop the affected action if
unavailable. Never evade dedup with alternate paths or artificial ranges.
Raw skill_dir is this entry's directory. Loading does not restart coverage or
the frontier, reset a budget or replay work. Expansion requires the caller's release,
not a new grant inferred from selection.

Require the agreed scope (or explicitly released settled brief) and actual Build
findings/ledger in current context, not remembered summaries. Recover missing work
products from their named files or retained conversation records; on a card use
its body and checkpoint comments, not a presumed surviving scratch file. Follow
actual truncation. If the baseline or result remains unavailable, report it as
unverified and stop that check; use the kernel's blocking protocol on a card,
never kanban_complete on a fabricated Checked result. Request missing material,
not a fresh search or budget reset to reconstruct lost work.

</ReadBeforeWork>

# QA Search

Read checks for each delivered unit: [Lookup](references/lookup.md),
[Sweep](references/sweep.md), [Hunt](references/hunt.md).

Match actual results against the agreed scope, coverage, per-item fields, links,
freshness, done criteria and budget. Check retrieved-source records, not memory.
Report checked / unmet / unverified with concrete evidence and named gaps.
This is retrieval self-check, not a trust verdict, synthesis, rankings, caller
final acceptance or a new self numeric score. Preserve existing `REVIEW:` gates.

## Output template

```text
Checked: <scope/coverage/links/dates/fields and supporting records>
Unmet: <missing agreed requirement and evidence>
Unverified: <inaccessible evidence or open judgment>
Budget / continuity: <consumed, remaining, retained coverage/frontier>
Disposition: <deliver / bounded Build correction / Plan agreement needed>
Open for researcher: <verification, synthesis or adjudication still needed>
```

## Verification

All selected unit QA checks were applied; searched and unsearched ground match
the ledger. No unsupported pass, source-trust verdict or numeric self-score.
No approval, coverage, frontier or budget reset, and no external search in QA.

## Handoff

Corrections go to Build within the same scope and remaining budget; expansion
goes to Plan and client agreement. Deliver the complete unit report plus QA in
the final reply, with durable paths named in resident work. Cards retain the
kernel's needs_input/capability/scheduled/review protocols and end with
`kanban_complete` summary or `kanban_block`; scratch files are not delivery.
Preliminary Build + QA returns to refined Plan. Caller acceptance remains open.
Advance another unit only if already agreed and released for execution, retaining
results and consumed budget; an explicit caller review gate must be satisfied first.
