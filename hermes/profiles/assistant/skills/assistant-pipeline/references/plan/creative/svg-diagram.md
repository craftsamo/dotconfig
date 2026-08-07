# SVG diagram — decision surface

Precise architecture, scientific, educational, or general concept
diagrams as self-contained HTML + inline SVG. Hand-drawn editable
feel → `excalidraw-diagram.md`; information-led generated art →
`infographic.md`.

Technic `creator-svg-diagram` · QA `svg-diagram` · deterministic,
zero generation spend · card: `deterministic-render` when data and
format are fully settled.

## Fix before release

- Mode: architecture (software/cloud/infra) vs concept
  (educational/scientific/general).
- The exact content: labels (verbatim), node/edge relationships,
  groupings — the diagram is wrong if any label drifts.
- Requested dimensions/`viewBox` and light/dark behavior.
- Delivery: the HTML master plus a rendered PNG preview is always
  produced; name any additional export.

## Defaults

- Anchor: none — determinism replaces it; a diagram series shares
  one locked visual language.
- Budget shape: zero generation; iteration cost is turns, not spend.
