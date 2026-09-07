---
name: video-creator-pipeline
description: >-
  Root of video-creator's clip and authored-UI-tour leaves. Load first for a filled form naming
  generate-clip, edit-clip, analyze-clip or create-tour, then load only that leaf.
  Not an interview, a video menu, or a generic movie-making workflow.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [video, hands, pipeline]
    category: hands
---

<Run>

1. Read `skill`, `intent`, `deliver`, optional `budget`, and `form`.
   Load the named leaf. Validate required fields, types, local paths and
   options (`other: true` accepts a described value). Return one batched
   `Q<n>:` for missing/unusable fields; unknown leaf: `no skill fits`.
   Analyze may omit `deliver`; its evidence stays in a fresh scratch dir.
   A2A's loopback IP is normal transport metadata, not a missing form field;
   the transport does not authenticate a profile name. Never ask the caller
   to prove its role by saying "I am Creator".
2. Load only the leaf's selected references and previous delivery for
   `intent: revise`. Reuse surviving intermediates before any new spend.
3. Follow `<Procedure>`; no TTS, image generation, outside skills or
     improvised movie frameworks. create-tour permits task-local HTML/CSS/GSAP
     UI authoring under its concrete leaf contract; helpers freeze/check/render,
     not dictate UI layout. Never edit managed scripts or frozen project source.
    Shared clip helper:
   `python3 ${HERMES_SKILL_DIR}/scripts/clip-media.py --help` (from leaves,
   `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py --help`).
4. Run `<QA>`. Append each finding to the job's `qa.md` before the next
   visual call. Samples are not whole-video verification. Use only the
   bounded looks the leaf names; do not loop on "one more to be sure".
5. Reply with `<Report>`, including failures and missing checks. Media
   generation budget counts attempts including failures; analysis has
   separate bounded calls. Never patch a managed skill at runtime.

</Run>
