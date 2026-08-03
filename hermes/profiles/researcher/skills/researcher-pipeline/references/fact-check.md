# Fact-check mode — claim-by-claim verdicts

Loaded when the task presents specific external claims, cited sources, or
current specifications to verify. A final artifact may be supplied so the
claims can be extracted verbatim, but the deliverable remains a verdict per
claim, not an artifact-quality gate or a survey of the topic. The core <Method>
applies scoped to each claim — corroboration and counterevidence matter more
than breadth.

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
for QA to consume. Do not judge the artifact's craft, rendering, mechanical
specification, completeness, or fit to its brief.

## QA handoff artifact

When the body names QA as a consumer, write the complete Output template to
the requested attachment (default `claim-ledger.md`) and attach it before
completion. Include every source URL/id, reliability/credibility score,
counterevidence, and unverifiable gap. QA reads this immutable ledger; the
completion summary remains only a notification headline. The completion handoff
uses `metadata.artifact_handoff.qa` with `status: evidence`, `consumer: qa`, and
`ledger: <attached filename>`, alongside the artifact name and verification
result.

Without an attached ledger, complete with exactly one `metadata.completion`
envelope whose role metadata names `mode: analyze`, `deliverable: fact-check`,
sources, coverage, confidence, and open gaps.

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
- QA-bound work attached the complete claim ledger named in Output.
