---
name: build-verify
description: >-
  Verify, Build stage: trace each agreed claim to its origin, corroboration
  and counterevidence, assign confidence-rated verdicts, write the ledger,
  self-check and deliver. Requires the client's agreement from Plan; not an
  open investigation, option comparison or consumer directives.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, verify, build]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Build>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="build-verify")`. Reuse only full bodies in
current context, never a past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../../references/gather.md). Reading strategy does not authorize searches.
Evidence from a chain or from Hyperliquid also requires its shared reference:
[EVM](../../references/platforms/evm.md), [Solana](../../references/platforms/solana.md) or
[Hyperliquid](../../references/platforms/hyperliquid.md).
A technic the brief names or [Capabilities](../../references/capabilities.md)
matches is loaded too with `skill_view(name="<technic>")`; it adds to this mode
and never replaces it.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/../../references/gather.md`
and `${HERMES_SKILL_DIR}/../../references/platforms/<chain>.md` as applicable.
Follow `next_offset` through actual truncation; if recovery fails, stop the
affected action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Verify: Build

Use for specific external claims, cited sources or current specifications.
The output is claim-level verdicts, never a survey or an artifact-quality gate.
Corroboration and counterevidence matter more than breadth.

## Build

Apply the kernel's Build Method to the agreed fixed claims and source
requirements. A moving list or topic-survey expansion returns to Plan; it
never silently changes the release.

1. Decompose compound sentences into individually checkable claims using the
   agreed mapping. Preserve each source claim byte-for-byte as a verbatim code
   span/block, including punctuation and Unicode; add a separate neutral
   investigation restatement. Never normalize apostrophes, quotes, dashes,
   spacing, numbers or capitalization. Preserve the original even when split.
2. Per claim, hunt the origin (who first said it and in what context), then
   independent corroboration, then counterevidence. Prefer primary sources
   over coverage. Repetition across outlets sharing one origin counts once.
3. Assign `supported` / `refuted` / `partly true` / `unverifiable` with confidence
   and both trust axes. Let credibility do the work: a single B-source yes is
   "probably true", not "supported". Check literal content and intended reading
   when the literal reading would be a strawman; say which was evaluated.
4. Stop when stable: two independent A/B sources agreeing, or a primary source
   directly settling it, ends the hunt. Do not imply two-source credibility 1
   when only one primary source directly settles the matter. Within the budget,
   seek counterevidence per claim, not only once for the whole topic.

### Artifact-supplied claims

Inspect final text, image, video or audio only to transcribe exact factual
claims and their context, then verify against external sources. Do not
paraphrase so loosely that the checked proposition differs from the artifact.
If exact extraction cannot be established, report the transcription uncertainty;
never pretend an inferred transcript is byte-for-byte evidence. Return
claim-level verdicts for caller QA, not judgments of craft, rendering,
mechanical specification, completeness or fit to brief.

### Durable QA ledger

When downstream quality assurance consumes the verdicts, write the complete
Output template to the brief's requested file (default `claim-ledger.md`) at
the durable path before finishing. Include every original claim, verdict,
confidence, URL/id, reliability/credibility score, counterevidence and open gap.
Name the file in the reply; a one-line summary never replaces this full record.
If the destination is missing, request it rather than invent a durable path.

## Output template

```markdown
## Verdicts
1. Original (verbatim): `<exact source claim>`
   - Restatement: <neutral investigation restatement; subclaim mapping if compound>
   - Verdict: **<verdict>** (confidence high/med/low)
   - Evidence: <key sources, what each shows> [Reliability; Credibility]
   - Counterevidence: <what contradicts, or "none found" and search scope>
   - Context: <origin, caveats, omissions that change the reading>
## Sources
- <URL/id> - <author/publisher>, <date>; Reliability <A-F>; Credibility <1-6>
## Notes
- <compound claims and how split; unverifiable claims, why, what was searched and where evidence might live>
```

"Unverifiable" must state what was searched and where evidence might live.
Report any need for a follow-up investigate unit to caller instead of expanding
into a survey. Check the ledger and report against Verification below.

## Verification

Reconcile the fixed input claims, their exact source text and the actual report
and ledger. This is claim-evidence self-check, not artifact-quality acceptance.

- Every input claim has an original, neutral restatement, verdict, confidence,
  cited evidence, counterevidence and relevant context; no inconvenient or
  unverifiable claim was dropped.
- Originals match source claims byte-for-byte, including punctuation, Unicode,
  apostrophes, quotes, dashes, spacing, numbers and capitalization. Compound
  claims retain their whole original and an explicit subclaim mapping. A
  paraphrase or uncertain artifact transcription is not claimed as an exact copy.
- Verdicts use `supported` / `refuted` / `partly true` / `unverifiable` and track
  credibility. A single B-source affirmation is not promoted to supported.
  Two independent A/B sources or a directly settling primary support a stable
  verdict; one primary does not masquerade as two independent confirmations.
- Load-bearing origins are traced; shared-origin echoes are not counted twice.
  Counterevidence was searched per claim, not merely per topic. Literal and
  contextual readings are distinguished when a literal reading is a strawman.
- "None found" is bounded by the search performed; "unverifiable" states what
  was searched, why evidence is missing and where it might live. All sources
  carry URL/id, publisher/date and reliability/credibility scores.
- Downstream-QA-bound work wrote the complete Output ledger at the requested
  durable path, default filename `claim-ledger.md`, and named it in the report.
  Inspect that file, not a one-line summary: all claims, verdicts, confidence,
  sources, scores, counterevidence and open gaps must be there.
- Artifact inspection stayed limited to exact claims and context; no craft,
  rendering, mechanical, completeness or artifact-vs-brief verdict was produced.

Report missing ledger/evidence as unmet or unknown, not caller acceptance or a
self-score. An exact-copy repair or in-scope evidence correction stays in
Build within remaining budget. Changed claims, a topic survey or expanded
source hunt needs [plan-verify](../plan/SKILL.md) and agreement;
preserve originals and prior budget.

## Handoff

Build ends, in the same turn, with the self-check against this entry's
Verification, and the reply carries what it found unmet or unknown; the
kernel's Build section says how the findings are delivered. Keep this mode for
the unit; another kind of question is another agreed unit with its own
entries, never a silent switch.
