# Meme — decision surface

Classic-template or custom-scene memes with deterministic captions.
Exact typography cards without a joke structure → `text-card.md`.

Technic `creator-meme` · QA `text-visual` · deterministic
composition (custom generated scene = separate budgeted stage) ·
resident-only (humor is taste — cards can't carry it).

## Fix before release

- The joke: premise, audience, tone — and the **joke structure**
  (dilemma, preference, escalation, denial), which drives template
  selection more than topic does.
- Mode: `classic-template` (known caption fields) vs `custom-scene`
  (supplied or separately budgeted generated background).
- Captions, verbatim — mark any exact-whitespace/line-break
  invariant explicitly; otherwise wrapping is renderer-owned.
- Destination and its safety bar; content must not be hateful,
  abusive, or personally targeted — that line is yours to hold, not
  the creator's to discover.

## Defaults

- Anchor: none; the template identity + provenance are recorded in
  the report. Third-party template commercial rights stay
  unconfirmed — relay that caveat with the deliverable.
- Budget shape: zero for template composition; a generated scene
  uses a separate `generated-image` line.
