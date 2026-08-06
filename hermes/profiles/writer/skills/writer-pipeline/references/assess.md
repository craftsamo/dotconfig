# Assess mode — writing judgment without a deliverable

Loaded when the kernel's ModeRouting picks Assess: the task wants the
writer's JUDGMENT — how to shape a future text, or what's wrong with an
existing one — not new deliverable prose.

Two branches; pick by what the task supplies:

| The task supplies | Branch |
| --- | --- |
| A goal/brief for a text that doesn't exist yet | Consultation |
| An existing text to evaluate | Critique |

Both branches: **no deliverable prose.** Illustrative fragments (a sample
heading, a one-line hook, a single rewrite sample) are fine; drafting
sections is not. An assess task that turns out to need the actual text is
reported as such — never silently written.

## Consultation (Plan-Loop writing advice)

The orchestrator is mid-Plan-Loop and needs writing judgment fast: how a
deliverable should be structured, which tone/medium/type fits, how much
work it is.

- **Time-boxed.** Answer from the brief + the norms-stack knowledge
  (which japanese-* layers would apply, per the kernel TypeTable) + a
  quick look at any supplied reference text.
- **Assume, don't block, by default** — label assumptions; block (per the
  operating contract's STATE/Q<n> protocol) only when every plausible
  reading changes the verdict.

Assessment format:

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<recommended shape in one line — e.g. "tutorial article, 3 sections, 敬体">
## Structure
<proposed outline: sections/units and what each carries, 3-6 lines>
## Tone & norms
<tone axes recommendation and which norms layers apply>
## Effort
<rough size: length range, review passes, inputs the writer would need>
## Risks
<audience mismatch, source gaps, terminology traps>
## Assumptions
<what you assumed instead of asking, labeled>
```

## Critique (evaluate an existing text)

Run the four passes of `references/review.md` in **critique usage**:
findings with location / pass / severity / one-line fix, then a single
verdict line (`ship as-is` / `fix blockers` / `restructure`) plus the
highest-leverage fix. If the text is a script, apply the
`references/script.md` unit contract in the structure pass.

- Read the text's own brief/constraints first if supplied; critique
  against ITS goals, not your taste.
- Cite the specific checklist item (skill + rule) behind every norms
  finding.

## Report

- Final report = the assessment or critique; write it to the durable
  path when long (kanban mode: also `kanban_attach`).
- The reply/summary = 1-2 plain sentences carrying the verdict.

## Pitfalls

- Writing the opening "as an example" and drifting into the actual draft.
- Recommending a structure without checking the supplied inputs/reference
  texts the brief names.
- Blocking on tone detail an assumption + label would cover (full
  ToneCalibration belongs to the write task, not the consultation).
- Critique that rewrites: one sample line is illustration; a corrected
  paragraph is a deliverable.
