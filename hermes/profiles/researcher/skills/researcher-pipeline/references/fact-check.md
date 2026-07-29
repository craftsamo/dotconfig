# Fact-check mode — claim-by-claim verdicts

Loaded when the task presents specific claims to verify — or an artifact to
check against a spec (the artifact-check variant below). Narrow and fast:
the deliverable is a verdict per claim, not a survey of the topic. The core
<Method> applies scoped to each claim — corroboration and counterevidence
matter more than breadth.

## Procedure

1. **Decompose** the input into individually checkable claims (a compound
   sentence may hide three). Restate each neutrally — don't inherit the
   asker's framing.
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
1. "<claim, restated neutrally>" — **<verdict>** (confidence high/med/low)
   - Evidence: <key source(s), what each shows> [Reliability · Credibility]
   - Counterevidence: <what contradicts, or "none found">
   - Context: <origin, caveats, what the claim omits — when it changes the reading>
## Sources
- <URL/id> — <author/publisher>, <date> · Reliability <A–F> · Credibility <1–6>
## Notes
- <claims that were compound and how they were split; anything unverifiable and why>
```

## Artifact-check variant — deliverable vs spec, pass/fail

Loaded shape when the "claims" are spec items and the subject is an artifact
(a render, file, document, dataset) — usually a gating QA check on another
worker's output. Same discipline, different evidence source:

- **The artifact is the primary source.** Inspect it directly — vision for
  visual content, metadata for numbers (media figures via the
  `media-artifact-verification` technic when pinned), file reads for text.
  Never verdict from the producing task's own description of its output.
- **Spec items are the claims.** Decompose the spec into individually
  checkable items; a vague item ("looks consistent") gets restated as the
  most checkable reading, labeled as such.
- **Verdict per item**: `pass` / `fail` / `can't verify` (with what blocked
  it). Then one **overall gate verdict**: pass only when every gating item
  passes — anything else is fail or can't-verify, never "mostly fine".
- Record what was **not** inspected (frames not sampled, fields not in
  metadata) — exclusions are part of the verdict.

Output: the Verdicts template above with spec items as claims, plus an
`## Overall` line carrying the gate verdict and the failing/unverified items.

## Pitfalls

- Verifying the vibe of the claim instead of its literal content (or vice
  versa when the literal reading is a strawman — check both, say which).
- (Artifact check) Trusting the producer's self-report or filename instead
  of inspecting the artifact; passing a gate on "no obvious problems"
  without walking every spec item.
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
