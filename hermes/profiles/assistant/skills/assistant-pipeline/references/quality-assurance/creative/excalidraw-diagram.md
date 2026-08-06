# QA contract — Excalidraw diagram

The orchestrating assistant performs a read-only inspection of the editable Excalidraw diagram at its durable path.

## Scope
Inspect the actual `.excalidraw` JSON and a compatible rendered preview. Preserve
editability while checking the source-preview agreement; do not flatten or fix it.

## Required inputs
The JSON file at its durable path, expected schema/version, elements and grouping
requirements, exact labels/relationships, and a compatible Excalidraw renderer.
Research evidence supplied in the flow is required for external factual claims.

## Checks
1. Parse JSON read-only. Validate required document fields, unique element IDs,
   element types, bound-element references, bindings, and groups.
2. Check that every referenced element exists, no orphan or reciprocal binding is
   broken, and the elements remain editable rather than a screenshot.
3. Render with a compatible application/path and compare source geometry, text,
   connectors, clipping, overlap, and theme with the preview and brief.
4. Record source and preview evidence with bounded findings in the verdict/feedback.

## Not verified / never do
Invalid JSON/schema, orphan references, unavailable compatible render, or missing
research evidence supplied in the flow for a gating fact means NOT verified —
obtain the missing input or state plainly it cannot be checked. Do not edit JSON,
repair bindings, redraw, flatten, re-export, or publish.
