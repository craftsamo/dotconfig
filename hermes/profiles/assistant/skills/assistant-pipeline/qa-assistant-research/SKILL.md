---
name: qa-assistant-research
description: "QA research: test conclusions against load-bearing sources. Inspect evidence, counterevidence and scope by unit; return retrieval gaps to search, never accept unsupported reasoning."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["quality-assurance", "research"]
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

# Research QA — the per-unit gate

Open the load-bearing sources — never judge a conclusion from the
reply's prose. The common floor in `../references/quality-assurance/index.md` applies; the
researcher's own floors (citation integrity, evidence/inference
separation) are its non-waivable side, and your gate is
evidence-based on top, per unit. Searcher retrieval gates through
`../qa-assistant-search/SKILL.md`.

## The gate — every research unit

Use the agreed proposal or explicitly released settled brief as the acceptance
baseline, including approved changes, scope and budget. A Plan proposal is not
a researched conclusion. For purpose-first work, require the primary-relayed
agreed research proposal/scope: questions, done criteria, source policy, budget
and approved changes (explicitly none when unchanged). The primary owns that
agreement; Assistant must not reconstruct it from the original purpose.
Alternatively use the explicitly authorized original settled brief only while
unchanged. Missing relayed baseline or authorized original settled brief means
unverified: request the missing baseline as a spec-gap through the primary.
No acceptance from purpose alone, conclusions alone or specialist self-QA.
Researcher's specialist QA is a self-check, not an
external pass: the immediate primary Client independently accepts its evidence,
and Assistant still gates the returned deliverable. Do not copy the public
specialist QA procedure here or relax any scoring, criteria or correction limit.

1. **Evidence check** — every nontrivial claim traces to a scored
   source, a direct observation, or a stated uncertainty; per-claim
   confidence present; counterevidence was searched, not just
   confirmation. A conclusion without its evidence is not gateable.
2. **Source spot-check** — open the load-bearing URLs: they
   resolve, the quotes match, the dates/versions are right; a
   citation the researcher never retrieved fails the unit
   regardless of the rest.
3. **Completeness check** — measure against the brief's done
   criteria: sub-questions closed, every option scored on every
   criterion (or explicitly `Unknown`), every claim verdicted, every
   decision point closed or explicitly open.
4. **Boundary check** — conclusions only: no crafted artifact
   slipped in, no artifact-quality verdicts, inference never
   presented as observation; a defect traced to a consumed search
   part goes back as a search gap, not a researcher fault.
5. **Verdict** — pass → accept; the conclusion becomes a part
   (`../execute-assistant-research/SKILL.md`) or the delivery. Fail →
   itemized, scope-anchored feedback through the same route the
   unit traveled (the consuming primary's session or peer request).

## Contract files

| Unit | Contract |
| --- | --- |
| Evidence-pack — synthesis of an open question | `references/evidence-pack.md` |
| Tradeoff-matrix — options × criteria + recommendation | `references/tradeoff-matrix.md` |
| Fact-check — per-claim verdicts | `references/fact-check.md` |
| Guidance — directives for a downstream worker | `references/guidance.md` |

## Handoff note

A part fails its CONSUMER's needs (a ledger your QA pass cannot
adjudicate from, guidance the writer cannot act on without the
sources) → the defect returns through the consuming primary's same
conversation as a normal feedback turn when the brief asked for it,
or to Plan as a spec gap when it did not; the consumer never re-researches.
