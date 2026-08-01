---
name: qa-svg-diagram
description: Read-only QA inspection of an immutable SVG diagram source and render.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, svg, diagram, parsing, rendering]
    category: technic
---

<Scope>
Inspect the actual SVG/HTML attachment and its rendered preview. This is a
source-structure and visual contract, not a production, cleanup, or export task.
</Scope>

<RequiredEvidence>
The immutable source and digest, expected dimensions/theme/content, required
accessibility constraints, and a compatible render path. Researcher evidence is
needed for externally factual diagram claims.
</RequiredEvidence>

<ChecksProcedure>
1. Hash the source, parse it with a read-only XML/SVG check, and remeasure
   width, height, viewBox, namespaces, IDs, text, and link references.
2. Confirm it is self-contained: resolve fonts, images, CSS, markers, and
   `use` references; report missing or external assets that the brief forbids.
3. Render a preview and inspect all nodes, connectors, text, clipping, overlap,
   contrast, links, and required accessibility names/roles. Compare preview
   content with source structure and expected relationships.
4. Return exact evidence and findings to `qa-pipeline` for verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
Parse failure, missing required asset, unavailable render, or unprovided
Researcher evidence for a gating fact is `can't_verify`. Never edit SVG, inline
assets, fix labels, regenerate, re-export, or publish the candidate.
</FailOrCantVerify>
