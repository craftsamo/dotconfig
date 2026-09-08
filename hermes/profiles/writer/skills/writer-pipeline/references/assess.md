# Assess mode — writing judgment without a deliverable

Loaded when the kernel's ModeRouting picks Assess: the task wants the
writer's JUDGMENT — how to shape a future text, or what's wrong with an
existing one — not new deliverable prose.

At the v7 entry point, check the installed leaf before using legacy advice.
An existing script uses `analyze-script`, not the old script unit contract or
four-pass review below. The same rule holds for every served family. If a
consultation later receives an actual draft, reselect the operation at the
v7 kernel; consultation is not a back door to legacy critique.

Two branches; pick by what the task supplies:

| The task supplies | Branch |
| --- | --- |
| A goal/brief for a text that doesn't exist yet | Consultation |
| An existing text to evaluate | Critique |

Both branches: **no deliverable prose.** Illustrative fragments (a sample
heading, a one-line hook, a single rewrite sample) are fine; drafting
sections is not. An assess task that turns out to need the actual text is
reported as such — never silently written.

## Consultation (Plan-mode writing advice)

The assistant runs this consultation during Plan mode when a session brief
needs writing judgment: how a deliverable should be structured, which
tone/medium/type fits, and how much work it is. The judgment is delivered in
the assistant's reply.

- **Time-boxed.** Answer from the brief, the selected leaf's form/requirements
  and supplied reference text. For scripts, use the actual consumer's fields
  and bounds. Do not choose a universal panel count, balloon cap, speaking rate
  or mandatory CTA from `references/script.md` for a served job. A proposed
  bound is a decision for the requester, not measured producer evidence.
  Legacy TypeTable/layers apply only to an explicitly legacy, unserved job.
- **Assume, don't block, by default** — label assumptions; ask in the reply
  and wait only when every plausible reading changes the verdict.

Assessment format:

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<recommended shape in one line — e.g. "tutorial article, 3 sections, 敬体">
## Structure
<proposed outline: sections/units and what each carries, 3-6 lines>
## Tone & norms
<tone recommendation and the selected leaf's relevant requirements>
## Effort
<rough size: length range, review passes, inputs the writer would need>
## Risks
<audience mismatch, source gaps, terminology traps>
## Assumptions
<what you assumed instead of asking, labeled>
```

## Critique (evaluate an existing text)

For a served family, use its `analyze-<subject>` leaf and report contract instead.
Only an explicitly legacy, unserved job runs the four passes of
`references/review.md` in **critique usage**:
findings with location / pass / severity / one-line fix, then a single
verdict line (`ship as-is` / `fix blockers` / `restructure`) plus the
highest-leverage fix. Retained `references/script.md` is compatibility material,
not a second contract for served script analysis or pre-draft script advice.

- Read the text's own brief/constraints first if supplied; critique
  against ITS goals, not your taste.
- Cite the specific checklist item (skill + rule) behind every norms
  finding.

## Report

- Final report = the assessment or critique. For a consultation, the judgment
  is the deliverable in the reply; for a long critique, write the report to
  the durable path named by the session brief and name that path in the reply.
- The reply carries the verdict in 1-2 plain sentences when a separate report
  file is used.

## Pitfalls

- Writing the opening "as an example" and drifting into the actual draft.
- Recommending a structure without checking the supplied inputs/reference
  texts the brief names.
- Blocking on tone detail an assumption + label would cover (full
  ToneCalibration belongs to the write task, not the consultation).
- Critique that rewrites: one sample line is illustration; a corrected
  paragraph is a deliverable.
