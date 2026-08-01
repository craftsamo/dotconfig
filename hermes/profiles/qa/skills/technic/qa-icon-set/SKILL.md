---
name: qa-icon-set
description: Read-only QA inspection of an immutable logo-derived icon set.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, icons, logo, favicon, maskable]
    category: technic
---

<Scope>
Inspect the delivered icon files and unmodified approved source anchor. Verify
identity fidelity and platform packaging; do not redraw, normalize, or publish.
</Scope>

<RequiredEvidence>
The immutable source and digest, approved first-party/source record, complete
manifest of requested sizes and formats, alpha/background and maskable safe-zone
rules, and destination requirements. Researcher evidence settles external
provenance or rights; QA checks the package against it.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and decode every manifest item; remeasure dimensions, format, alpha,
   file size, and required naming. Check the manifest is complete.
2. Compare rendered marks to the approved source for exact fidelity, variant,
   proportions, and identity at each size, especially the smallest size.
3. Inspect for blur, resampling distortion, unintended recolor/crop, unsafe
   maskable margins, and background/alpha violations; check safe-zone geometry.
4. Return evidence and findings to `qa-pipeline`'s verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
Missing source/provenance evidence, incomplete manifest, undecodable file, or
unavailable required size render is `can't_verify`. Do not alter the mark,
regenerate sizes, infer rights, re-export, or publish.
</FailOrCantVerify>
