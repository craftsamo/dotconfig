---
name: creator-pixel-video
description: >-
  Creator's deterministic leaf technic for pixel animation: sprite/cel motion,
  native-grid redraw, procedural loops, particles, and integer-step camera work,
  encoded as lossless-master MP4 and optional compatibility/GIF outputs with
  measurable palette, cadence, motion, and loop-seam QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, pixel-video, sprite-animation, loop, gif]
    category: technic
---

<Goal>

Animate pixel assets without destroying their grid. Pixel video is not ordinary
generated video with a retro prompt: every frame remains intentional on the
native grid, and temporal claims are verified numerically.

</Goal>

<Scope>

Use for sprite animation, character cycles, logo/scene loops, environmental
effects, parallax made from integer steps, and pixel-art MP4/GIF delivery.
Ordinary model-generated video belongs to `creator-generated-video`.

</Scope>

<Inputs>

The MediaBrief must pin the source pixel asset or a preceding
`creator-pixel-art` stage, native grid, protected static regions, motion intent,
duration, effective cadence, loop requirement, destination size/codec, palette,
and required master/compatibility formats.

</Inputs>

<ProductionRules>

- Animate on the native grid. Redraw sprites/cels or re-threshold from a
  high-resolution construction per frame.
- Never rotate, subpixel-translate, blur, or interpolate a finished bitmap.
- Name which regions may move and which must remain identical across frames.
- Prefer 8-12 unique frames/second for a stepped pixel cadence, duplicated into
  a 24 fps container when required.
- Camera movement, zoom, and parallax use integer pixel steps only.
- A procedural opt-in backend such as `pixel_art_video.py` may supply rain,
  snow, embers, or fireflies, but it is only an effect backend; it cannot stand
  in for requested sprite or character motion.
- Build a true cycle. Do not duplicate the first frame as the last encoded
  frame; verify the last-to-first transition instead.

</ProductionRules>

<Procedure>

1. Lock one motion statement: what changes, what stays fixed, and why the motion
   exists. Story or character action needs a cel/sprite plan before rendering.
2. Produce native-resolution numbered PNG frames and inspect a contact sheet.
3. Encode with `${HERMES_SKILL_DIR}/scripts/encode-pixel-video.sh`; it uses
   nearest-neighbor integer scaling and an RGB-lossless `libx264rgb` master.
   yuv420p is compatibility output only.
4. Run the verifier with self-contained dependencies against the actual encoded
   file, passing every contract value and the native source frames for the
   master. A successful ffmpeg exit is not acceptance evidence:
   `uv run --no-project --with Pillow --with numpy python
   ${HERMES_SKILL_DIR}/scripts/verify-pixel-video.py <master.mp4> --master --grid WxH
   --scale N --palette-max N --effective-fps N --container-fps N --loop
   --source-pattern 'frames/frame_*.png'`.
   Verify the compatibility copy separately with the same contract values and
   `--compat`, omitting `--source-pattern`.
5. Inspect motion over time, not only the first frame. Use the pipeline's
   corrective allowance for a brief miss, not for unbounded taste exploration.

</Procedure>

<Verification>

- Native grid and output scale are exact integer multiples.
- Palette is stable across frames; no anti-aliased/interpolated colors leak in.
- Effective fps matches the brief independently of container fps.
- The wrap diff is within the normal frame-step range when a loop is required.
- Protected regions remain invariant; requested parts visibly move or deform.
- Master and compatibility copies are labeled; the RGB-lossless master is not
  silently replaced by a YUV/chroma-subsampled rendition.
- Contact sheet, verifier output, source/seed, and final artifacts are attached.

</Verification>
