# QA contract — pixel art

The orchestrating assistant performs a read-only inspection of the native-grid pixel-art image at its durable path.

## Scope
Inspect the native pixel-art master, its integer nearest-neighbor review copy,
and any batch. Do not resample, retouch, recolor, or treat a preview as master.

## Required inputs
The native master at its durable path, exact grid, fixed palette/color cap,
alpha/silhouette rules, integer preview scale, protected features, and batch
palette anchor if applicable.

## Checks
1. Remeasure native width/height, unique colors, palette entries,
   alpha/transparency, and file format.
2. Inspect pixels for anti-aliasing, intermediate colors, blur, non-integer
   geometry, broken silhouette, and transparency violations.
3. Verify the preview dimensions are an integer multiple and each native pixel is
   one uniform nearest-neighbor block; compare every batch item to the same
   palette anchor and inspect destination readability.
4. Record measured evidence and bounded findings in the verdict/feedback.

## Not verified / never do
Missing native master/palette, non-decodable artifact, or unmeasurable preview
mapping means NOT verified — obtain the missing input or state plainly it cannot be
checked. A grid, palette, alpha, or fidelity mismatch is a verdict/feedback
finding; never repair, upscale, quantize, regenerate, or publish.
