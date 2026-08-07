# Excalidraw diagram — decision surface

An **editable** hand-drawn-style diagram delivered as valid
`.excalidraw` JSON — the deliverable is the editable document, never
a flattened image. Precision/exact rendering → `svg-diagram.md`.

Technic `creator-excalidraw-diagram` · QA `excalidraw-diagram` ·
deterministic, zero generation spend · card:
`deterministic-render` when content is fully settled.

## Fix before release

- The exact content: labels, relationships, groupings, theme
  intent — as for SVG, label fidelity is an invariant.
- Why editability matters here (collaboration, later edits by the
  user) — if nobody will edit it, `svg-diagram.md` renders better.
- Upload/share: explicit only — the default is a local file; an
  Excalidraw link or upload must be requested in the spec.

## Defaults

- Anchor: none — deterministic.
- Budget shape: zero generation. A compatible rendered preview
  always accompanies the JSON for review.
