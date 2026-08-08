# QA contract — pixel video

The orchestrating assistant performs a read-only inspection of the native-grid pixel video artifact at its durable path.

## Scope
Apply the full `qa-video` temporal contract plus pixel-specific checks to the
actual encoded artifact and sampled frames. Never accept a first-frame check.

## Required inputs
The video artifact file at its durable path, expected duration/fps/container fps,
native grid, palette, scale, protected regions, effective cadence, and loop
requirement. Research evidence supplied in the flow is required for external
factual claims.

## Checks
1. Reprobe video metadata as in `qa-video`, then sample frames across motion and
   scene boundaries, including the wrap when looping.
2. Measure native-grid dimensions, integer scale, palette stability, color count,
   and per-frame absence of interpolation, blur, and anti-aliased colors.
3. Check effective frame timing versus container fps, protected-region invariance,
   requested motion, audio/text sync, and last-to-first seam behavior.
4. Record measured frame/timecode evidence in the verdict/feedback.

## Not verified / never do
Missing source grid/palette, insufficient frame samples, unreadable probe, or
missing research evidence supplied in the flow means NOT verified — obtain the
missing input or state plainly it cannot be checked. Do not rescale, re-encode,
re-time, redraw frames, repair seams, or publish.
