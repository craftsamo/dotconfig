---
name: creator-excalidraw-diagram
description: >-
  Creator's editable leaf technic for Excalidraw diagrams delivered as
  validated, compatible .excalidraw JSON.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, excalidraw, diagram, editable, collaboration]
    category: technic
---

<Goal>

Produce an editable Excalidraw document, not a flattened image. The canonical
dispatch identity is `creator-excalidraw-diagram`; the official Excalidraw
skill is only its implementation engine.

</Goal>

<Contract>

`creator-pipeline` owns the MediaBrief, Budget, Review gate, delivery, and one
single batched `Q<n>:` block. Never call the official skill's `clarify`.
Load the official implementation from `external_dirs` with
`skill_view(name="excalidraw")`; do not copy its contents here. Upload is
never implicit: perform it only when the brief explicitly requests it.

</Contract>

<Procedure>

1. Read the validated brief and preflight the official skill, source inputs,
   Excalidraw schema/version, and a compatible render path. Block before
   production or acceptance if a dependency or preview path is unavailable.
2. Use the official Excalidraw engine to create the editable `.excalidraw`
   JSON. Preserve exact labels, relationships, theme intent, and source data;
   do not substitute a screenshot or silently publish an external link.
3. Mechanically validate JSON syntax, required document fields, unique element
   IDs, element references, bindings, and bound-element consistency.
4. Generate a preview through an Excalidraw-compatible renderer or the real
   application, inspect it with vision, and check text, geometry, overlap,
   connectors, clipping, and light/dark appearance.
5. Save the JSON, preview, and validation evidence; attach final artifacts and
   hand the evidence to the pipeline for V1-V6 verification and delivery.

</Procedure>

<Verification>

- The file opens as editable Excalidraw JSON and passes the machine checks;
  required fields, IDs, bindings, and references are all valid.
- The preview matches the brief and has no unreadable text, broken binding,
  accidental overlap, clipping, or unverified rendering claim.
- Generation spend is zero. Record V1 acceptance, V2 mechanical, V3 visual,
  V4 consistency, V5 spend, and V6 attachment evidence for the pipeline.

</Verification>
