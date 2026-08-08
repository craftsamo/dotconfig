# QA contract — raster image

The orchestrating assistant performs a read-only inspection of the raster-image artifact file at its durable path.

## Scope
Inspect the actual raster artifact file at its durable path from the completed
Creator task. Use for generated images and article illustrations; do not inspect a
producer report as the artifact or replace checks for SVG, video, or data-specific
technics.

## Required inputs
The raster artifact file at its durable path, production task identity, expected
dimensions/aspect/crop, format and size limits, destination preview requirements,
and any approved style/set or source references. Research evidence supplied in the
flow is required for external factual claims; QA does not establish those claims.

## Checks
1. Open the actual file, and remeasure format, dimensions, channels/alpha, and
   byte size with read-only tools.
2. Inspect native pixels, the required destination crop, and a thumbnail. Check
   artifacts, accidental text or logos, anatomy, geometry, composition, contrast,
   crop safety, and brief-specific details.
3. Compare every item in a requested set for locked style, palette, scale,
   lighting, and recurring subject consistency; record exact locations.
4. Record evidence and bounded findings in the verdict/feedback.

## Not verified / never do
If the file cannot be opened, decoded, or rendered at a required size, or a
required source/style/research claim is absent, the result means NOT verified —
obtain the missing input or state plainly it cannot be checked. A measured
contract or visual defect is a verdict/feedback finding; do not repair, crop,
rewrite, regenerate, re-export, or publish it.
