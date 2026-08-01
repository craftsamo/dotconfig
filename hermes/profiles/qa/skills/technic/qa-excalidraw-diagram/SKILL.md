---
name: qa-excalidraw-diagram
description: Read-only QA inspection of an immutable editable Excalidraw diagram.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, excalidraw, diagram, editable, json]
    category: technic
---

<Scope>
Inspect the actual `.excalidraw` JSON and a compatible rendered preview. Preserve
editability while checking the source-preview agreement; do not flatten or fix it.
</Scope>

<RequiredEvidence>
The immutable JSON and digest, expected schema/version, elements and grouping
requirements, exact labels/relationships, and a compatible Excalidraw renderer.
Researcher evidence is required for external factual claims.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and parse JSON read-only. Validate required document fields, unique
   element IDs, element types, bound-element references, bindings, and groups.
2. Check that every referenced element exists, no orphan or reciprocal binding
   is broken, and the elements remain editable rather than a screenshot.
3. Render with a compatible application/path and compare source geometry, text,
   connectors, clipping, overlap, and theme with the preview and brief.
4. Return source and preview evidence with bounded findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Invalid JSON/schema, orphan references, unavailable compatible render, or missing
Researcher evidence for a gating fact is `can't_verify`. Do not edit JSON,
repair bindings, redraw, flatten, re-export, or publish.
</FailOrCantVerify>
