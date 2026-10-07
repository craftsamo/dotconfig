---
name: qa-assistant-search
description: "QA search: open sources and verify retrieval coverage. Gate lookup, sweep and hunt findings before handoff; do not infer coverage or silently resolve questions for researcher."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["quality-assurance", "search"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/quality-assurance/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/quality-assurance/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Search QA — the per-unit gate

Open the actual links — never judge retrieval from the reply's
prose. The common floor in `../references/quality-assurance/index.md` applies; the searcher's
own floors (link integrity, retrieval-only output, dated claims)
are its non-waivable side, and your gate is evidence-based on top,
per unit.

## The gate — every search unit

Use the agreed proposal or explicitly released settled brief as the acceptance
baseline, including approved changes, scope and budget; eligible cards retain
their settled card-body contract. A Plan proposal is not retrieved findings.
Searcher's specialist QA is a self-check, not an external pass: the requester
performs independent acceptance. Do not copy the public specialist QA procedure
here or relax any scoring, criteria or correction limit.

1. **Evidence check** — findings carry per-claim sources with
   dates; the coverage statement matches the unit type (sweep:
   matrix + floor; hunt: source map + trail notes + gaps); labeled
   interpretation present when the brief was assumed-on. A missing
   coverage statement means not gateable.
2. **Link spot-check** — open the load-bearing URLs: they resolve,
   the quotes match, the dates/versions are right. A reconstructed
   or pattern-filled URL fails the unit regardless of the rest.
3. **Coverage check** — measure against the brief's claim: floor
   counts met, exclusions honored, freshness window respected; for
   `survey-enumeration` / `exhaustive-hunt` cards, measure against
   the coverage claim in the card body.
4. **Boundary check** — retrieval only: no verdicts, rankings, or
   recommendations slipped in; open judgments named under
   `Open for researcher`, not silently resolved.
5. **Verdict** — pass → accept; the findings become a part
   (`../execute-assistant-search/SKILL.md`) or the delivery. Fail →
   itemized, scope-anchored feedback to the same session — or, for
   cards, a narrowed gap-fill card of the same unit.

## Contract files

| Unit | Contract |
| --- | --- |
| Lookup — specific sourced answer | `references/lookup.md` |
| Sweep — enumeration / survey | `references/sweep.md` |
| Hunt — exhaustive multi-hop hunt | `references/hunt.md` |

## Handoff note

A part fails its CONSUMER's needs (a table missing the fields the
decision needs, a source map the researcher cannot adjudicate
from) → the defect returns to the searcher session as a normal
feedback turn when the brief asked for it, or to Plan as a spec gap
when it did not; the consumer never re-retrieves.
