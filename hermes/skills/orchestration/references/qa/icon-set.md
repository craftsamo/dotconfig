# QA contract — icon set

The orchestrating assistant performs a read-only inspection of the logo-derived icon set at its durable paths.

## Scope
Inspect the delivered icon files and approved source anchor. Verify identity
fidelity and platform packaging; do not redraw, normalize, or publish.

## Required inputs
The source file at its durable path, approved first-party/source record, complete
manifest of requested sizes and formats, alpha/background and maskable safe-zone
rules, and destination requirements. Research evidence supplied in the flow
settles external provenance or rights; QA checks the package against it.

## Checks
1. Decode every manifest item; remeasure dimensions, format, alpha, file size,
   and required naming. Check the manifest is complete.
2. Compare rendered marks to the approved source for exact fidelity, variant,
   proportions, and identity at each size, especially the smallest size.
3. Inspect for blur, resampling distortion, unintended recolor/crop, unsafe
   maskable margins, and background/alpha violations; check safe-zone geometry.
4. Record evidence and findings in the verdict/feedback.

## Not verified / never do
Missing source/provenance evidence, incomplete manifest, undecodable file, or
unavailable required size render means NOT verified — obtain the missing input or
state plainly it cannot be checked. Do not alter the mark, regenerate sizes,
infer rights, re-export, or publish.
