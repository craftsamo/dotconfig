---
name: fact-check-researcher
description: >-
  Verify fixed claims; return sourced claim verdicts. Use for a
  fixed claims list with source requirements, each claim resolved to a
  verdict with evidence and counterevidence. Not for open synthesis
  (evidence-pack), option comparisons (tradeoff-matrix), consumer guidance
  (guidance), topic surveys, or artifact-quality/crafting verdicts.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel and shared gather reference.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, fact-check]
---

<ReadBeforeWork>

Before working this entry, load the current researcher-pipeline kernel's full
body (unit discipline, source evaluation, citation rules, and the card gate)
with `skill_view(name="researcher-pipeline")` — reuse only a full
current-context body, never a summary or a past load record. Direct entry
into this unit still requires the kernel body first.

Gathering beyond a few direct lookups needs the gather engine: call
`skill_view(name="researcher-pipeline", file_path="references/gather.md")` —
see [Gather](../references/gather.md).

If `skill_view` returns unchanged while a full body is missing, or cannot
return a required body, fall back to `read_file` on the
canonical paths — `${HERMES_SKILL_DIR}/../SKILL.md` for the kernel,
`${HERMES_SKILL_DIR}/../references/gather.md` for the gather engine, and
`${HERMES_SKILL_DIR}/SKILL.md` for this entry — following `next_offset` only
for actual truncation, never an artificial range or an alternate path to
dodge dedup. If the body still cannot be recovered, stop the affected
research rather than proceed without it.

A selection change is not a new grant: if the request needs a missing or
wider unit scope than what was released, return that gap to the requester
and keep the original job scope — never restart or self-expand it.

This entry does no card work: the kernel refuses every kanban card with
`kanban_block(kind=capability)` before any research begins.

</ReadBeforeWork>

# Fact-check unit — claim-by-claim verdicts

Loaded when the released unit presents specific external claims, cited
sources, or current specifications to verify (a fixed claims list +
source requirements settled in the brief — resident or A2A peer; the
retired `claim-verification` card form is refused at the card gate).
A final artifact may be supplied so the claims can
be extracted verbatim, but the deliverable remains a verdict per claim,
not an artifact-quality gate or a survey of the topic. The core <Method>
applies scoped to each claim — corroboration and counterevidence matter
more than breadth. A moving claims list is a spec-gap finding; a claims
list sprouting a topic survey is a granularity finding.

## Procedure

1. **Decompose** the input into individually checkable claims (a compound
   sentence may hide three). Preserve each source claim byte-for-byte as a
   verbatim code span/block, including punctuation and Unicode; then add a
   separate neutral restatement for investigation. Never silently normalize
   apostrophes, quotes, dashes, spacing, numbers, or capitalization.
2. Per claim: hunt the **origin** (who first said it, in what context),
   then independent corroboration, then counterevidence. Prefer primary
   sources over coverage of them.
3. **Verdict** per claim: `supported` / `refuted` / `partly true` /
   `unverifiable` — with the credibility score doing the work (a single
   B-source yes = "probably true", not "supported").
4. Stop when the verdict is stable — two independent A/B sources agreeing
   (or a primary source directly settling it) ends the hunt.

## Output template

```markdown
## Verdicts
1. Original (verbatim): `<exact source claim>`
   - Restatement: <claim restated neutrally for investigation>
   - Verdict: **<verdict>** (confidence high/med/low)
   - Evidence: <key source(s), what each shows> [Reliability · Credibility]
   - Counterevidence: <what contradicts, or "none found">
   - Context: <origin, caveats, what the claim omits — when it changes the reading>
## Sources
- <URL/id> — <author/publisher>, <date> · Reliability <A–F> · Credibility <1–6>
## Notes
- <claims that were compound and how they were split; anything unverifiable and why>
```

## Artifact-supplied claims

When the claim appears in a final text, image, video, or audio artifact, inspect
that artifact only to transcribe the claim byte-for-byte and its context
accurately. Then
verify it against external sources using the normal procedure. Return the
claim-level `supported` / `refuted` / `partly true` / `unverifiable` verdicts
for the assistant's quality-assurance pass to consume. Do not judge the
artifact's craft, rendering, mechanical
specification, completeness, or fit to its brief.

## Quality-assurance ledger artifact

When the brief names the assistant's quality-assurance pass as a consumer,
write the complete Output template
to the requested file (default `claim-ledger.md`) at the durable path
before finishing. Include every source URL/id, reliability/credibility
score, counterevidence, and unverifiable gap. The assistant's quality-assurance
pass reads this ledger; the report names the file, and the ledger remains the
complete record.

## Pitfalls

- Verifying the vibe of the claim instead of its literal content (or vice
  versa when the literal reading is a strawman — check both, say which).
- Paraphrasing an artifact's claim so loosely that the checked proposition is
  no longer what the final artifact says.
- Treating repetition across outlets that share one origin as
  corroboration — trace to the origin first.
- Expanding into a full topic survey — out of scope; note it for a
  follow-up evidence-pack task instead.
- "Unverifiable" without stating what was searched and where it might live.

## Verification

- Every input claim has a verdict with confidence and cited evidence;
  counterevidence was searched per claim, not just per topic.
- Origins traced for load-bearing claims; shared-origin echoes not counted
  twice.
- Quality-assurance-bound work wrote the complete claim ledger named in Output
  to the durable path.
