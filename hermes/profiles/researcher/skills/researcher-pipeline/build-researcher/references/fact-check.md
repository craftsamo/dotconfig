# Build a Fact Check

Apply Build's Method to the agreed fixed claims and source requirements.
Corroboration and counterevidence matter more than breadth. A moving list or
topic-survey expansion returns to Plan; it never silently changes the release.

## Procedure

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

## Artifact-Supplied Claims

Inspect final text, image, video or audio only to transcribe exact factual
claims and their context, then verify against external sources. Do not
paraphrase so loosely that the checked proposition differs from the artifact.
If exact extraction cannot be established, report the transcription uncertainty;
never pretend an inferred transcript is byte-for-byte evidence. Return
claim-level verdicts for caller QA, not judgments of craft, rendering,
mechanical specification, completeness or fit to brief.

## Durable QA Ledger

When downstream quality assurance consumes the verdicts, write the complete
Output template to the brief's requested file (default `claim-ledger.md`) at
the durable path before finishing. Include every original claim, verdict,
confidence, URL/id, reliability/credibility score, counterevidence and open gap.
Name the file in the reply; a one-line summary never replaces this full record.
If the destination is missing, request it rather than invent a durable path.

"Unverifiable" must state what was searched and where evidence might live.
Report any need for a follow-up evidence-pack to caller instead of expanding
into a survey. Pass the ledger and report to Researcher QA for self-check.
