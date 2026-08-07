# Knowledge comic — decision surface

Educational, biography, or tutorial comics: storyboarded panels,
consistent characters, deterministic lettering. Single explanatory
visuals → `infographic.md` / `svg-diagram.md`.

Technic `creator-knowledge-comic` · QA `comic` · metered page art +
deterministic lettering · resident-only (multi-stage by nature).

## Fix before release

- The source material and its fact/quote ledger — claims, numbers,
  and quotations are invariants the panels must carry unaltered.
- Audience, tone, and the learning sequence (what the reader knows
  after each page).
- Cast: the recurring characters and their consistency definitions.
- Page count, reading order, panel density, safe areas — approved
  at the storyboard stage before any page art.
- Lettering: exact dialogue/captions (writer work when substantial,
  QA-passed) — composed deterministically, never model-generated
  lettering.

## Defaults

- Anchor: REQUIRED for multi-page work — the approved storyboard +
  character definitions + one sample page lock continuity before
  the page batch (a comic is a composite: storyboard → pages →
  lettering, per `composite-media.md`).
- Budget shape: 4 variants per page, failures count; regeneration
  targets only the named page, everything else is preserved.
