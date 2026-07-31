---
name: creator-manim-explainer
description: >-
  Creator's deterministic leaf technic for Manim educational video: concept,
  equation, algorithm, data, paper, and 3D explainers with staged renders,
  readback QA, and exact ffmpeg delivery. The creator-pipeline owns intake,
  Budget, review, and delivery.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, manim-video, explainer, education, animation]
    category: technic
---

<Goal>
Produce an educational Manim video whose mathematical, algorithmic, or paper
content is correct, legible, and timed for learning. This is a leaf technic with
canonical identity `creator-manim-explainer`, not an alternate pipeline.

</Goal>

<Scope>
Use for concept, equation, algorithm, data, paper, and 3D modes. Load the
official `manim-video` engine from `external_dirs` with
`skill_view(name="manim-video")`; keep its rendering conventions and scripts
authoritative rather than duplicating them here.

</Scope>

<PipelineContract>
- The creator-pipeline owns the MediaBrief, Budget, Review, delivery, and one
  single batched `Q<n>` block for missing decisions. Do not use an official-skill
  `clarify` flow or create a separate question protocol.
- Save a project-specific `plan.md` and script. Use draft, render, and final
  stages, then hand the outputs and evidence to pipeline V1-V6.
- Do not use inline interpreter commands: invoke the project script or an
  official script. Handshake optional voice synthesis as `core:tts` with its
  concrete backend and count every synthesis against the pipeline's TTS cap.

</PipelineContract>

<Preflight>
Check Python 3.10+, Manim Community Edition >=0.20, `ffmpeg`, and all declared
fonts. If any scene uses MathTex, check the required LaTeX toolchain and packages
as well. Validate assets, output permissions, and the destination's resolution,
aspect, duration, and codec before rendering. Resolve the loaded official
skill's directory before using its `scripts/setup.sh` for diagnosis; do not use
this wrapper's `HERMES_SKILL_DIR`, and do not install anything without explicit
authorization. Missing prerequisites block the work and must be reported to the
pipeline.

</Preflight>

<Procedure>
1. Load `skill_view(name="manim-video")`, lock the lesson objective, audience,
   notation, scene order, narration/subtitle timing, and delivery contract in
   `plan.md`.
2. Implement one Manim class per scene. Keep equations, labels, colors, camera
   framing, and transitions explicit; do not let a scene silently depend on
   mutable state from another scene.
3. Render a `-ql` draft and inspect stills at representative states. Read every
   equation and label back at delivery size; correct clipping, overlap, opacity,
   contrast, and pacing before a high-quality render.
4. Render the final with `-qh`, stitch scene outputs with the official/project
   script, and preserve the source, plan, logs, stills, and intermediate files.
5. Run `ffprobe`; inspect multiple frames across every scene and verify duration,
   frame rate, audio/subtitle timing, transitions, and stream metadata.

</Procedure>

<Verification>
Acceptance requires educational accuracy, equation and label readback, readable
font sizing, correct timing, intentional opacity, subtitle alignment when used,
and no clipped or contradictory state. Attach draft/final evidence, still
inspections, ffprobe output, QA notes, and the stitched artifact for the V1-V6
handoff. Do not treat a successful Manim or ffmpeg exit as visual acceptance.

</Verification>
