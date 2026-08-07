# Text card — decision surface

OG / social / title cards whose **exact copy and typography** must
render correctly — text is composed deterministically over a
background, never generated into pixels.

Technic `creator-text-card` · QA `text-visual` · deterministic
composition (a generated background is a separate budgeted stage) ·
card: `deterministic-render` when copy + background are settled.

## Fix before release

- The exact copy, verbatim — every character, line break, and brand
  term is an invariant.
- Target dimensions, safe area, and the unfurl/thumbnail context it
  must survive.
- Typography: font (available on this machine), palette, hierarchy.
- Background: one of — a supplied image, a solid/gradient direction,
  or an explicitly budgeted generated background
  (`generated-image.md` as its own Part with its own spend line).

## Defaults

- Anchor: none for one card; a card series locks one composition
  template.
- Budget shape: zero for composition; the generated-background line
  is separate and explicit.
