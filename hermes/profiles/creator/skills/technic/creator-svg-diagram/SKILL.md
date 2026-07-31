---
name: creator-svg-diagram
description: >-
  Creator's deterministic leaf technic for precise architecture and concept
  diagrams delivered as self-contained HTML with inline SVG.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, svg, diagram, architecture, visualization]
    category: technic
---

<Goal>

Produce an exact, inspectable diagram without generation spend. This leaf
combines the `architecture-diagram` mode with the optional `concept-diagrams`
mode; it is not a parallel intake or delivery pipeline.

</Goal>

<Routing>

- Route software, cloud, and infrastructure diagrams to `architecture`.
- Route educational, scientific, physical, and general-concept diagrams to
  `concept`.
- The canonical dispatch identity is `creator-svg-diagram`, even when the
  implementation engine is loaded from an official skill in `external_dirs`.

</Routing>

<Contract>

`creator-pipeline` owns the MediaBrief, Budget, Review gate, delivery, and one
single batched `Q<n>:` block. Never call the official skill's `clarify`.
Load the implementation engine with `skill_view(name=...)`; do not copy its
contents into this adaptation layer.

</Contract>

<Procedure>

1. Read the validated brief and load the selected official mode with
   `skill_view(name="architecture-diagram")` or
   `skill_view(name="concept-diagrams")`; preflight its inputs, fonts/assets,
   and a headless-browser (or equivalent) HTML-to-PNG render path.
   Block before production or acceptance if a dependency or render path is
   unavailable.
2. Build one self-contained HTML file with inline SVG. Preserve exact labels,
   connectors, `viewBox`, requested dimensions, and light/dark behavior.
3. Render the HTML to PNG, inspect it with vision, and check connector routing,
   overlap, clipping, contrast, and legibility at native and small sizes.
4. Save the final HTML and the verification preview/evidence in the task
   workspace; attach only final deliverables and required reuse artifacts.
5. Hand the evidence and artifacts to the pipeline for V1-V6 verification,
   including mechanical spec checks, visual review, and delivery attachment.

</Procedure>

<Verification>

- Confirm the diagram mode, exact text, node/edge relationships, `viewBox`,
  dimensions, format, and requested theme behavior.
- Confirm no unintended overlap, hidden connector, clipping, or unreadable
  label remains in the rendered PNG; an unrenderable HTML file is not done.
- Record V1 acceptance, V2 mechanical, V3 visual, V4 consistency, V5 spend
  (zero), and V6 attachment evidence for `creator-pipeline`.

</Verification>
