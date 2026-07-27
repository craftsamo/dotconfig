# Advisory mode — Plan-Loop writing consultations

Loaded when <ModeRouting> detects an advisory task. The orchestrator is
mid-Plan-Loop with the user and needs writing judgment fast: how a
deliverable should be structured, which tone/medium fits, how much work it
is — not the text itself.

## Rules

- **No deliverable prose.** Illustrative fragments (a sample heading, a
  one-line hook) are fine; drafting sections is not.
- **Time-boxed.** Answer from the brief + the norms stack knowledge
  (japanese-writing / tech-prose / prose-rhythm applicability) + a quick
  look at any supplied reference text.
- **Assume, don't block, by default** — label assumptions; block (per the
  operating contract's STATE/Q<n> protocol) only when every plausible
  reading changes the verdict.

## Assessment format

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<recommended shape in one line — e.g. "tutorial article, 3 sections, 敬体">
## Structure
<proposed outline: sections and what each carries, 3-6 lines>
## Tone & norms
<tone axes recommendation (register/temperature/distance/assertiveness)
 and which norms layers apply (japanese-writing / tech-prose / rhythm)>
## Effort
<rough size: length range, review passes, inputs the writer would need>
## Risks
<audience mismatch, source gaps, terminology traps>
## Assumptions
<what you assumed instead of asking, labeled>
```

## Report

- Final message = the assessment (attach via `kanban_attach` if long).
- `kanban_complete` summary = 1-2 plain sentences carrying the verdict.

## Pitfalls

- Writing the opening "as an example" and drifting into the actual draft.
- Recommending a structure without checking the supplied inputs/reference
  texts the brief names.
- Blocking on tone detail an assumption + label would cover (full
  ToneCalibration belongs to the write task, not the consultation).

## Verification

- Deliverable follows the format: verdict + structure + tone/norms +
  effort + risks; assumptions labeled; no deliverable prose produced.
