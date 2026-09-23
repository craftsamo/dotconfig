---
name: create-motion
description: >-
  Create an authored motion-graphics video (launch/promo, brand or sizzle
  piece, feature reveal, kinetic type, logo sting; 3..60s, 30fps) that
  VideoCreator designs and draws itself in HTML/CSS/SVG/GSAP, optionally
  matching a local reference video. Storyboard first; authors and renders
  locally only after Creator relays approval of that exact storyboard. Not UI
  task tours, CTA-bound claim ads, learning explainers, generated footage,
  image generation, TTS or music.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "numbered storyboard + hash; HyperFrames source, draft/final MP4, contact sheets, qa.md"
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

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns the client's
   meaning, rights and approvals; you own the concept execution: beats,
   layout, typography, drawn visuals, motion, transitions and self-QA. Draw
   what the piece needs yourself (SVG/CSS/HTML: UI mock-ups, icons, flags,
   device frames, marks). You have no image generation, TTS, music or SFX:
   a raster asset, a voice or a soundtrack the storyboard needs is a
   dependency request back to Creator, never invented and never substituted
   silently. `reference_use: reproduce` of a third-party brand, logo or copy
   needs the client's permitted-use statement in `note`; without it, treat
   the reference as inspiration and say so.
2. Reference (optional, bounded). Extract frames locally
   (`python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py --help`, or
   `ffmpeg` fps=4 contact sheets) and estimate the soundtrack's tempo/drops
   with local `ffmpeg` measurements. Look at contact sheets, not single
   frames: at most 12 `vision_analyze` looks for the whole analysis, each
   finding appended to `qa.md` before the next look. Record beats, timing,
   copy, palette, type feel, camera/transition techniques and audio hit
   points. Remote video analysis is out of scope.
3. Before creative decisions read [authoring](references/authoring.md) and
   the kernel's [craft reading](../../references/craft.md) (motion + visual).
   Then read the shared HyperFrames policy through the parent skill:

   ```text
   skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
   ```

   Attempt the applicable technical lookups, report unavailable references
   and continue with local authoring.
4. Round A (no `approved_plan`): write `storyboard.md` per
   [authoring](references/authoring.md) — front matter, beats table covering
   0..duration, verbatim on-screen copy, design tokens, motion language,
   drawn-vs-supplied asset plan, and an audio plan with tempo, energy curve
   and hit times precise enough for audio-creator to score to. Unresolved
   needs go in `pending` (e.g. `audio`, `image:hero`). Then run:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/motion.py propose --storyboard <draft storyboard.md> --out <deliver>/proposal-v<N>
   ```

   Report the proposal path, SHA-256, status (`awaiting-approval` or
   `pending-inputs`) and the pending list with what each needs, then STOP.
   A budget or a brief is not approval. Choose the next unused N on revision.
5. Round B (`approved_plan` + `approval_sha256` relayed by Creator in the
   same work conversation): author a fresh `<deliver>/source/` per
   [authoring](references/authoring.md): one `index.html`, local assets,
   vendored GSAP copied from `../tour/assets/`. Build hero frames first,
   then motion, then transitions. Iterate with draft renders:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/motion.py render --approved-plan <proposal-vN/storyboard.md> \
     --approval-sha256 <hash> --source <deliver>/source --out <deliver>/draft-<k> --quality draft
   ```

   Review each draft through its `sheet.png` (one look per sheet, findings to
   `qa.md` first), fix, and re-render. Bound: at most 4 drafts. An approved
   storyboard with pending items allows authoring and silent drafts only.
6. Final: when every pending item is resolved (Creator returns the files;
   place them under `source/assets/` and list them in an `inputs` JSON), run
   the same command with `--quality final --inputs <inputs.json>` into a new
   `<deliver>/final/`. It verifies the approval hash, strict lint, canvas,
   duration, audio presence and true peak, and writes `render.json` +
   `sheet.png`. A FAIL is fixed in source and re-rendered into a new
   directory, never waived. Changed beats, copy, duration or aspect need a
   new storyboard and approval; small execution fixes inside the approved
   storyboard do not.
7. Long commands use `background: true` and polling within the tool's
   actual timeout. No network, installs, upgrades or external workflows.

</Procedure>

<QA>

- Storyboard fidelity: every beat appears in order within ±0.25s of its
  approved window; on-screen copy is verbatim; the design tokens and motion
  language are the approved ones. With `reproduce`, compare final sheets
  against the reference sheets beat by beat and list every visible gap.
- Craft: continuous camera/transition logic (no unplanned hard cuts or
  dead frames), readable type at native size, no clipped or overlapping
  text, hierarchy per beat, eased motion with holds long enough to read.
- Audio: hits land on the storyboard's times; true peak < 0 dBTP (measured
  by the helper, never a listening claim); silence only when the approved
  storyboard says `audio: none`.
- Technical: helper PASS on canvas, fps, duration, audio presence and lint;
  source kept with the delivery.
- Sampled sheets are not whole-video or listening evidence: keep temporal
  and audio perception `unverified` until a human watches it.

</QA>

<Report>

`create-motion`; Round A: storyboard path + SHA-256, status, pending list
with the dependency request for each (producer, spec, timing), and the STOP.
Round B/final: source/draft/final paths, approved storyboard hash, each
helper RESULT JSON, qa.md findings with the gaps that remain, input files
used, `spend: media generation 0`. Include any HyperFrames references
consulted or found unavailable, with the local-authoring fallback used, per
the shared reference policy.

</Report>
