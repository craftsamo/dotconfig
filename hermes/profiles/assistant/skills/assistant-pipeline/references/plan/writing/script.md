# Script — decision surface

Producer-facing text a downstream pipeline turns into another
medium: comic scripts, storyboards, screenplays, timed video
scripts, TTS narration. Two audiences at once — the end audience
shapes the content, the producer shapes the format — and the
producer's contract is a DECISION, not a style choice: a script
that cannot be typeset or rendered deterministically has failed
regardless of how well it reads.

Writer type `script` · QA `script` · units: outline unit (story
beats) first for multi-page/multi-scene work; whole small job for a
short script.

## Fix before release

- **The downstream producer** — which pipeline consumes this
  (creator comic unit, TTS voice unit, video production, human
  artist) and its **field conventions**: either the producer's own
  field list, or an explicit "writer defaults apply". The producer
  addresses work by unit number — the numbering contract comes from
  here.
- **Quantities & budgets** — page/panel/scene count, duration,
  per-unit text caps (balloon character limits, beats per second)
  as the brief's numbers; the writer counts against them, it does
  not choose them.
- **Speaker roster** — who speaks, each speaker's register, fixed
  once for the whole work.
- **Story intent** — the end audience, the one idea the piece
  lands, and the action wanted from the viewer at the end.
- **Artifact contract** — the exact file name/path the producer
  expects.
- **Done criteria** — e.g. "renderable by the comic unit without a
  single clarifying question".

## Defaults

- Multi-page/multi-scene work: outline unit first (beat list, one
  line per unit) — approved before any dialogue is written.
- The QA-passed script is a **part**: it feeds the creator's units
  (a TTS card requires exactly such a final script) or an
  engineering/marketing consumer — release the consuming unit only
  after this one passes QA.
- Revisions never renumber units — dropped units are marked, and
  the producer's addressing stays stable.

## Red flags

- An undecided producer ("we'll figure out who renders it") — the
  format contract has no owner; spec-gap.
- Budgets left to feel ("make the balloons readable") — caps are
  numbers in the brief.
- A script briefed and its consuming production released in the
  same breath — the frontier rule exists precisely here.
