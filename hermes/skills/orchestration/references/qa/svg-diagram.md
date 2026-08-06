# QA contract — SVG diagram

The orchestrating assistant performs a read-only inspection of the SVG diagram source and render at their durable paths.

## Scope
Inspect the actual SVG/HTML artifact file at its durable path and its rendered
preview. This is a source-structure and visual contract, not a production,
cleanup, or export task.

## Required inputs
The source file at its durable path, expected dimensions/theme/content, required
accessibility constraints, and a compatible render path. Research evidence
supplied in the flow is needed for externally factual diagram claims.

## Checks
1. Parse the source with a read-only XML/SVG check, and remeasure width, height,
   viewBox, namespaces, IDs, text, and link references.
2. Confirm it is self-contained: resolve fonts, images, CSS, markers, and `use`
   references; report missing or external assets that the brief forbids.
3. Render a preview and inspect all nodes, connectors, text, clipping, overlap,
   contrast, links, and required accessibility names/roles. Compare preview
   content with source structure and expected relationships.
4. Record exact evidence and findings in the verdict/feedback.

## Not verified / never do
Parse failure, missing required asset, unavailable render, or unprovided research
evidence supplied in the flow for a gating fact means NOT verified — obtain the
missing input or state plainly it cannot be checked. Never edit SVG, inline assets,
fix labels, regenerate, re-export, or publish the candidate.
