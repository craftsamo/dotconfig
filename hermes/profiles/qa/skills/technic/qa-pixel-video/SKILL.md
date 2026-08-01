---
name: qa-pixel-video
description: Read-only QA inspection of an immutable native-grid pixel video.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, pixel-video, palette, cadence, loop]
    category: technic
---
<Scope>
Apply the full `qa-video` temporal contract plus pixel-specific checks to the
actual encoded artifact and sampled frames. Never accept a first-frame check.
</Scope>

<RequiredEvidence>
The immutable video and digest, expected duration/fps/container fps, native grid,
palette, scale, protected regions, effective cadence, and loop requirement.
Researcher evidence is required for external factual claims.
</RequiredEvidence>

<ChecksProcedure>
1. Reprobe video metadata as in `qa-video`, then sample frames across motion and
   scene boundaries, including the wrap when looping.
2. Measure native-grid dimensions, integer scale, palette stability, color count,
   and per-frame absence of interpolation, blur, and anti-aliased colors.
3. Check effective frame timing versus container fps, protected-region invariance,
   requested motion, audio/text sync, and last-to-first seam behavior.
4. Return measured frame/timecode evidence to `qa-pipeline`'s verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
Missing source grid/palette, insufficient frame samples, unreadable probe, or
missing Researcher evidence is `can't_verify`. Do not rescale, re-encode,
re-time, redraw frames, repair seams, or publish.
</FailOrCantVerify>
