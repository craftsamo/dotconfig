# Writing QA — the per-unit gate

Read the actual file, whole — never judge from the reply summary.
The common floor in `../index.md` applies; the writer's own four
review passes (structure / norms / humanizer / integrity) are its
non-waivable floor, and your gate is evidence-based on top, per
unit.

## Outline gate — outline units

The cheap moment to catch the expensive defect:

- The structure serves the plan leaf's decisions: the claim is the
  spine (article), reader tasks map to sections (docs), units/beats
  cover the story with continuous numbering (script), the set's
  decomposition matches the plan.
- The tone samples land the decided register — pick one WITH the
  user when taste is theirs to judge; the choice binds the piece
  units that follow.
- Approving the outline fixes structure and tone: later piece
  feedback that reopens them is a plan change, not a revision.

## Full gate — piece units and whole jobs

1. **Evidence check** — the complete file at its durable path; the
   report itemizes the four passes, tone values, sources consulted,
   and labeled assumptions. A missing pass or an unnamed check
   means not gateable.
2. **Read it** — the whole file, against the brief: type, audience
   fit, register stability, length, required facts present.
3. **Source trace (spot-check)** — load-bearing claims, quotes,
   numbers, and URLs resolve to the pasted sources; marketing copy
   claims resolve to the project's **fact ledger**
   (`../../plan/marketing/marketing-state.md`). An unsupported
   claim fails the unit regardless of polish.
4. **Contract check** — route by deliverable family below; scripts
   additionally honor the producer's field conventions exactly
   (numbering continuous, verbatim fields instruction-free, budgets
   met by count).
5. **Verdict** — pass → accept; the text becomes a part
   (`../../execute/writing/index.md`) or the delivery. Fail →
   itemized, quote-anchored feedback to the same session, same
   unit.

## Contract files

| Deliverable family | Contract |
| --- | --- |
| Prose (copy, article, documentation) | `prose.md` |
| Script / storyboard / screenplay | `script.md` |

Japanese deliverables: notation consistency (表記ゆれ), register
stability, no LLM-smell filler — the writer's norms passes own the
checklists; you spot-check that they ran, citing the finding when
one clearly did not. Your spot-check has a mechanical arm: run
`uv run ~/.agents/skills/japanese-writing/scripts/lint.py --json
<delivered file> --genre <tech|business|essay>` on the actual file.
Detection is mechanical, judgment stays yours — findings are
feedback material to quote in an itemized fail, never a count gate,
and a clean lint does not by itself pass the unit. A cluster of
untriaged findings is evidence the writer's norms pass did not run.

## Handoff note

A part fails its CONSUMER's needs (a script the producer cannot
render, copy whose claim the marketer's inspection strikes) → the
defect returns to the writer session as a normal feedback turn; the
consumer never edits the part.
