---
name: create-promotion
description: >-
  Create an authored promotion video (product launch, promo, brand or sizzle
  piece, feature reveal, kinetic type, logo sting; 3..60s, 30fps) that
  VideoCreator designs and draws itself in HTML/CSS/SVG/GSAP, optionally
  matching a local reference video. A structure storyboard is approved first;
  the look is then iterated freely against the reference and a premium bar,
  and rendered locally. Not UI task tours, CTA-bound claim ads, learning
  explainers, generated footage, image generation, TTS or music.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "numbered storyboard + hash; HyperFrames source, draft/final MP4, reference comparison sheets, qa.md"
    form:
      subject: {required: true, type: text, label: "what the piece presents (product, brand, feature, event)"}
      what_for: {required: true, type: text, label: "purpose, destination and viewer; what they should feel/remember"}
      aspect: {required: false, options: ["16:9", "9:16", "1:1", "4:5"], label: "default 16:9; fixed dims per ratio, no cross-ratio crop/scale"}
      duration: {required: false, type: int, label: "3..60s; default 15, or the reference's length when reproducing"}
      reference: {required: false, type: file, label: "local reference video/image; analyzed locally, never uploaded"}
      reference_use: {required: false, options: [inspiration, reproduce], label: "default inspiration; reproduce = same beats/timing/look"}
      copy: {required: false, type: text, label: "exact on-screen lines the client fixed; else proposed in the storyboard"}
      assets: {required: false, type: path, label: "supplied logos/images/fonts/footage; absent = everything is drawn"}
      style: {required: false, type: text, label: "described look; free text is first-class"}
      direction: {required: false, type: text, label: "pacing/energy/transition language; free text"}
      audio: {required: false, type: file, label: "finished WAV, or JSON list of <=16 {source,start} cues from audio-creator"}
      approved_plan: {required: false, type: file, label: "Creator-relayed approval: exact proposal-vN/storyboard.md; absent = storyboard only"}
      approval_sha256: {required: false, type: text, label: "SHA-256 of that storyboard.md; required with approved_plan"}
      inputs: {required: false, type: file, label: "JSON {pending id: local path} resolving the storyboard's pending items"}
      note: {required: false, type: text, label: "rights/usage statement, must-keeps, anything else"}
---

<Standard>

The bar is a premium launch film by a senior motion designer, not a
template and not "close enough". Judge every frame against it:

- Scale: hero elements are big and confident; nothing important sits small
  in a sea of white unless the reference does exactly that.
- Depth: real 3D tilt, perspective, layered shadows, parallax and focus
  (blur) where the reference has them; flat cards are a gap, not a style.
- Type: display weight, tight tracking, per-word or per-letter staging,
  masks and blur-ins; secondary copy clearly subordinate.
- Motion: anticipation, overshoot and settle; eased value tweens for
  counters and bars; motion-matched seams so the film never cuts to a dead
  frame; hits land on the soundtrack.
- Density: the reference's level of detail (characters, props, UI texture,
  particles). An icon standing in for an illustration is a gap to close.

</Standard>

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns the client's
   meaning, rights and approvals; you own the whole execution: beats, layout,
   typography, drawn visuals, motion, seams and self-review. Draw what the
   piece needs yourself (SVG/CSS/HTML: UI screens, icons, characters, flags,
   device frames, marks). You have no image generation, TTS, music or SFX: a
   raster asset, voice or soundtrack the piece needs is a
   dependency request back to Creator, never invented or silently substituted. Reproducing a
   third-party brand, logo or copy needs the client's permitted-use
   statement in `note`; without it, treat the reference as inspiration.
2. Reference. Extract frames locally (`ffmpeg` fps=4, or
   `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py --help`) and
   measure the soundtrack's tempo, drops and hits with `ffmpeg`. Look at
   contact sheets, at most three images per step, and write each finding to
   `qa.md` before the next look. Record per beat: timing, copy, palette,
   type feel, scale of the hero element relative to the frame, depth,
   density, camera/seam technique and audio hits. Use as many looks as the
   analysis needs; stop when a new look adds nothing. No remote upload.
3. Before creative decisions read [authoring](references/authoring.md) and
   the kernel's [craft reading](../../references/craft.md) (motion + visual),
   then the shared HyperFrames policy through the parent skill:

   ```text
   skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
   ```

   Attempt the applicable technical lookups, report unavailable references
   and continue with local authoring.
4. Round A (no `approved_plan`): write `storyboard.md` per
   [authoring](references/authoring.md). It fixes STRUCTURE only: beat order
   and timing, verbatim on-screen copy, the look in words (palette,
   type family, mood, references), seams, and the audio plan (tempo, energy
   curve, hit times) precise enough for audio-creator to score to. It
   never fixes pixel sizes, positions, easing values or layout coordinates; those
   belong to iteration. Unresolved needs go in `pending`. Then run:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/promotion.py propose --storyboard <draft storyboard.md> --out <deliver>/proposal-v<N>
   ```

   Report the path, SHA-256, status and the pending list with what each
   needs, then STOP. A budget or a brief is not approval.
5. Round B (`approved_plan` + `approval_sha256` relayed by Creator in the
   same work conversation): author `<deliver>/source/` per
   [authoring](references/authoring.md). Build each beat's hero frame at
   full quality first, then motion, then seams. Render drafts with the
   reference attached so every draft comes with a side-by-side sheet:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/promotion.py render --approved-plan <proposal-vN/storyboard.md> \
     --approval-sha256 <hash> --source <deliver>/source --out <deliver>/draft-<k> --quality draft \
     [--reference <reference video>]
   ```

6. Improve loop, per draft: look at `compare.png` (reference above, draft
   below, same relative positions) or `sheet.png`, then write to `qa.md`
   the three biggest visible gaps against the reference and the Standard,
   ranked by how much they hurt the film. Fix those three by redesign, not nudges:
   redraw a scene, rebuild a layout, double a scale, add the missing depth
   or detail. A gap that survives two drafts must be attacked a different
   way. Everything that keeps the approved beats, copy, timing, seams and
   audio plan is in scope without new approval, however large the visual
   change. Continue until the remaining gaps are only ones you cannot close
   locally (a proprietary font, a photograph), up to 8 drafts. An approved
   storyboard with pending items allows authoring and silent drafts.
7. Final: when every pending item is resolved (Creator returns the files;
   place them under `source/assets/` and list them in an `inputs` JSON), run
   the same command with `--quality final --inputs <inputs.json>` into a new
   `<deliver>/final/`. It verifies the approval hash, strict lint, canvas,
   duration, audio presence and true peak. A FAIL is fixed in source and
   re-rendered into a new directory, never waived. Changed beats, copy,
   duration or aspect need a new storyboard and approval.
8. Long commands use `background: true` and polling within the tool's
   actual timeout. No network, installs, upgrades or external workflows.

</Procedure>

<QA>

- Structure: every beat appears in order within ±0.25s of its approved
  window; on-screen copy is verbatim; seams and audio hits as approved.
- Look: the final compare sheets meet the Standard; with `reproduce`, list
  every remaining visible gap against the reference beat by beat and say
  why it could not be closed.
- Craft: no unplanned hard cuts or dead frames, readable type at native
  size, no clipped or overlapping text, eased counters and bars.
- Audio: hits land on their times; true peak < 0 dBTP (measured by the
  helper, never a listening claim); silence only when the storyboard says
  `audio: none`.
- Technical: helper PASS on canvas, fps, duration, audio presence and lint;
  source kept with the delivery. Sampled sheets are not whole-video or
  listening evidence: temporal feel and listening stay `unverified`.

</QA>

<Report>

`create-promotion`; Round A: storyboard path + SHA-256, status, pending list
with the dependency request for each (producer, spec, timing), and the STOP.
Round B/final: source/draft/final paths, approved storyboard hash, each
helper RESULT JSON, the gaps closed per draft and the gaps that remain,
input files used, `spend: media generation 0`. Include any HyperFrames
references consulted or found unavailable, with the
local-authoring fallback used, per the shared reference policy.

</Report>
