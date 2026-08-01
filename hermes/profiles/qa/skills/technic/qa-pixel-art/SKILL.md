---
name: qa-pixel-art
description: Read-only QA inspection of an immutable native-grid pixel-art image.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, pixel-art, palette, sprite, nearest-neighbor]
    category: technic
---

<Scope>
Inspect the native pixel-art master, its integer nearest-neighbor review copy,
and any batch. Do not resample, retouch, recolor, or treat a preview as master.
</Scope>

<RequiredEvidence>
The immutable native master and digest, exact grid, fixed palette/color cap,
alpha/silhouette rules, integer preview scale, protected features, and batch
palette anchor if applicable.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and remeasure native width/height, unique colors, palette entries,
   alpha/transparency, and file format.
2. Inspect pixels for anti-aliasing, intermediate colors, blur, non-integer
   geometry, broken silhouette, and transparency violations.
3. Verify the preview dimensions are an integer multiple and each native pixel
   is one uniform nearest-neighbor block; compare every batch item to the same
   palette anchor and inspect destination readability.
4. Return measured evidence and bounded findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Missing native master/palette, non-decodable artifact, or unmeasurable preview
mapping is `can't_verify`. A grid, palette, alpha, or fidelity mismatch is a
pipeline finding; never repair, upscale, quantize, regenerate, or publish.
</FailOrCantVerify>
