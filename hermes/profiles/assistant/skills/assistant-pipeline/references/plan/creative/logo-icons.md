# Logo icon set — decision surface

Favicon / Apple / PWA / maskable / app-icon sets derived from an
**existing first-party SVG logo**. Third-party marks →
`brand-asset-sourcing.md`; a new mark is design work the user
approves separately — never a generated or redrawn trademark.

Technic `creator-logo-icons` · QA `icon-set` · deterministic, zero
generation spend · card: `deterministic-render`.

## Fix before release

- The source SVG (first-party, approved master) — its path is a
  required input; no source, no unit.
- The destination set list: which platforms/sizes (favicon, Apple
  touch, PWA, maskable, store icons) — "all the usual" is a
  decision, name it.
- Background/flattening rule per output (Apple output is flattened;
  maskable respects its safe zone) and `currentColor` handling.

## Defaults

- Anchor: the unmodified source SVG is the identity anchor and ships
  with the set.
- Budget shape: zero generation; 16 px legibility is the floor
  check — a mark that dies at 16 px is a user decision, not a
  creator fix.
