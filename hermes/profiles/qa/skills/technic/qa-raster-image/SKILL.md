---
name: qa-raster-image
description: Read-only QA inspection of an immutable raster-image candidate.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, raster, image, visual-inspection]
    category: technic
---

<Scope>
Inspect the actual raster attachment from the completed Creator parent. Use for
generated images and article illustrations; do not inspect a producer report as
the artifact or replace checks for SVG, video, or data-specific technics.
</Scope>

<RequiredEvidence>
The immutable file, production task identity, expected dimensions/aspect/crop,
format and size limits, destination preview requirements, and any approved
style/set or source references. Researcher evidence is required for external
factual claims; QA does not establish those claims.
</RequiredEvidence>

<ChecksProcedure>
1. Open the attachment, record its SHA-256, and remeasure format, dimensions,
   channels/alpha, and byte size with read-only tools.
2. Inspect native pixels, the required destination crop, and a thumbnail. Check
   artifacts, accidental text or logos, anatomy, geometry, composition,
   contrast, crop safety, and brief-specific details.
3. Compare every item in a requested set for locked style, palette, scale,
   lighting, and recurring subject consistency; record exact locations.
4. Return evidence and bounded findings to `qa-pipeline` for its verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
If the file cannot be opened, decoded, hashed, or rendered at a required size,
or a required source/style/Researcher claim is absent, report `can't_verify`
evidence to the pipeline. A measured contract or visual defect is a pipeline
finding; do not repair, crop, rewrite, regenerate, re-export, or publish it.
</FailOrCantVerify>
