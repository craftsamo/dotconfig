---
name: creator-ascii-video
description: >-
  Creator's deterministic leaf technic for ASCII video: video-to-ASCII,
  audio-reactive, generative, hybrid, lyrics, and TTS modes with rendered-frame
  inspection and exact ffmpeg delivery. The creator-pipeline owns intake, Budget,
  review, and delivery.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, ascii-video, audio-reactive, generative, lyrics]
    category: technic
---

<Goal>
Create readable, coherent ASCII motion while preserving the requested source,
palette, timing, and destination contract. This is a leaf technic, not a second
pipeline: the canonical identity is `creator-ascii-video`.

</Goal>

<Scope>
Use for video-to-ASCII conversion, audio-reactive meters and scenes, generated
ASCII animation, hybrid source/procedural pieces, lyric videos, and TTS-backed
ASCII delivery. Load the official `ascii-video` engine from `external_dirs` with
`skill_view(name=...)`; do not copy or reimplement that skill here.

</Scope>

<PipelineContract>
- The creator-pipeline owns the MediaBrief, Budget, Review, delivery, and one
  single batched `Q<n>` block for missing decisions. Never use an official-skill
  `clarify` flow and never ask questions outside that contract.
- Save a project-specific plan and executable script before rendering. Use the
  draft, render, and final stages, then hand artifacts and evidence to pipeline
  V1-V6. Do not run inline interpreter commands; use the project script or an
  official script so the worker guard can inspect the outer command.
- Meter generation is normally zero-cost. Handshake voice synthesis as
  `core:tts` with its concrete backend and count every synthesis against the
  TTS cap. Route image or video support through its canonical technic and
  account for it separately; do not hide supporting calls inside this technic.

</PipelineContract>

<Preflight>
Before production, check Python 3.10+, `numpy`, `scipy`, `Pillow`, `ffmpeg`, and
the required font. Verify the selected mode's inputs: source video for
video-to-ASCII, audio for audio-reactive or lyrics, a declared generator for
generative, source plus generator for hybrid, and text plus a TTS dependency for
TTS. Validate that the font contains every requested glyph and that its cell
metrics are stable. If anything is missing, block and report it; never install
automatically. The official setup script may be run only for diagnosis.

</Preflight>

<Procedure>
1. Load the official engine with `skill_view(name="ascii-video")`, confirm the
   MediaBrief and destination, and write `plan.md` plus a project script.
2. Lock cell size, brightness mapping, character set, palette, scene changes,
   frame rate, audio timing, loop/GIF requirements, and output dimensions.
3. Render representative keyframes first. Inspect glyph readability, brightness,
   character density, palette, and scene coherence before a full render.
4. Run the full render through the project or official script. Keep numbered
   frames, source inputs, parameters, and logs with the draft and final output.
5. Use `ffprobe` on the encoded result and inspect multiple frames, including
   scene boundaries. Check audio sync, duration, cadence, and stream metadata.
6. For loops, compare the wrap transition without duplicating an accidental seam;
   for GIFs, verify palette, frame count, timing, and size against delivery.

</Procedure>

<Verification>
Acceptance requires stable glyph geometry, brightness and character mapping,
palette discipline, scene coherence, readable text, and correct audio sync.
Review both dark/light extremes and several frames per scene, not only the first
frame. Attach the plan, script, keyframes, render log, ffprobe output, QA notes,
and final artifacts when handing the result through V1-V6.

</Verification>
