---
name: creator-html-motion
description: >-
  Creator's deterministic leaf technic for HyperFrames HTML/CSS motion,
  captioned video, product tours, overlays, and exact MP4/WebM delivery.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, hyperframes, html, motion-graphics, video, captions]
    category: technic
---

<Goal>
Render deterministic motion from HTML/CSS/JS while preserving the composition
source, visual system, seekable timing, media sync, and delivery evidence. The
canonical identity is `creator-html-motion`; the external `hyperframes` skill
router and its domain/workflow skills are the implementation engine.
</Goal>

<Scope>
Use for motion graphics, typographic/video overlays, product or website tours,
captioned narration, audio-reactive visuals, social promos, and other authored
HTML compositions rendered to MP4/WebM. Route p5.js interactive/generative
canvas work to `creator-p5js-experience`, math explainers to
`creator-manim-explainer`, and model-generated footage to
`creator-generated-video`.
</Scope>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
  HyperFrames workflow questions are translated into the pipeline's one batched
  block; they never create a second approval protocol.
- If `skill_view(name="hyperframes")` is missing, bootstrap the CLI-owned core
  set with `npx hyperframes skills update`, then resolve it again. A failed
  bootstrap or still-missing router blocks production.
- Once loaded, let `hyperframes` choose the current workflow and load its
  required domain skills. The stable dispatch identity remains
  `creator-html-motion`.
- HTML rendering itself has zero generation spend. TTS, generated images/video,
  music, or songs require their own capability handshake and Budget line.
- Never improvise from stale memory when a workflow/domain skill is missing.
  Run the router's targeted skills update; if it fails, block with its error.
- Preserve project source as the reusable master. A rendered video without its
  composition source and design/brief anchors is incomplete.
</Contract>

<Preflight>
Bootstrap a missing external `hyperframes` router first, then confirm it resolves
uniquely. Check the HyperFrames CLI, Node.js >=22, `ffmpeg`/`ffprobe`, headless
browser, fonts, assets, output space, and the selected workflow/domain skills.
Run `hyperframes doctor`; run the targeted workflow update required by the
router before reading that workflow.
Validate duration, fps, aspect/resolution, format/codec, safe areas, audio,
captions, source permissions, and destination size cap before scaffolding.
</Preflight>

<Procedure>
1. Route through the external HyperFrames entry skill, then transcribe the
   released spec's narrative, scenes/tracks, hero frames, design tokens, motion
   character, audio/captions, and delivery contract into the project brief/design
   files — an open decision among these is a spec gap, not yours to invent.
2. Scaffold non-interactively. Build each hero frame and inspect static layout
   before animation; register only deterministic, finite, seekable timelines.
3. Add transitions, audio, captions, and supporting assets under the selected
   workflow/domain contracts. Record every separately budgeted generation call.
4. Run strict lint, validation, layout inspection, and animation diagnostics.
   Render a draft, inspect representative frames and timing, then correct before
   the high-quality final render.
5. Probe the final streams and duration, inspect spread frames and scene
   boundaries, verify audio/caption synchronization, and preserve project source,
   logs, diagnostics, previews, and final artifacts for pipeline handoff.
</Procedure>

<Verification>
- Strict lint, contrast validation, layout inspection, and required animation
  diagnostics pass or every justified warning is recorded.
- Timelines are deterministic and seekable; no infinite repeat, wall-clock,
  async construction, off-frame content, overflow, or transition gap remains.
- `ffprobe` confirms duration, fps, dimensions, streams, codec/container, and
  file-size contract. Multiple frames per scene and all boundaries are visually
  inspected; audio and captions are checked against their source/timing.
- The composition project, design/brief anchors, diagnostics, and requested
  final video are attached according to pipeline delivery, with generated
  supporting assets and spend reconciled separately.
</Verification>
