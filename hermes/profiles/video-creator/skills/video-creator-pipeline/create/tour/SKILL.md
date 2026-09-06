---
name: create-tour
description: >-
  Create a task walkthrough from ordered local screenshots and explicit
  click/type targets, ending on a done screen. Produces a deterministic
  source project, preview frames and an optional MP4 of at most 60 seconds, with
  browser, macOS or mobile framing. Not URL capture, browser automation,
  a marketing film, arbitrary HTML motion, or speech synthesis.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "source project + preview frames; approved final MP4/SRT/poster/review/qa.md"
    form:
      task:
        required: true
        type: text
        label: "one task the viewer will accomplish; at most 60 characters"
      app:
        required: false
        type: text
        label: "application name; at most 40 characters"
      steps:
        required: true
        type: file
        label: "absolute local JSON manifest; screenshots, targets and final done screen"
      frame:
        required: false
        options: [auto, browser, macos, ios, android, none]
        label: "auto: browser for wide screenshots, ios for tall; decorative chrome, not OS detection"
      style:
        required: true
        options: [flat, glass, outline]
        references: references/styles/*.md
        label: "tour-local framing style"
      background:
        required: false
        options: [light, dark]
        other: true
        label: "light (default), dark, or six-digit #hex"
      backdrop:
        required: false
        type: image
        label: "optional local static image; cover-fit, cropping edges"
      accent:
        required: false
        label: "six-digit #hex; default #265ee8"
      destination:
        required: false
        options: [landscape, portrait]
        label: "1280x720 (default) or 720x1280; 30 fps"
      max_zoom:
        required: false
        label: "camera scale cap 1..2 (default 2); 1 keeps the full screenshot, without changing click targets"
      preview:
        required: false
        options: ["yes", "no"]
        label: "yes (default) stops after snapshots for approval; no authorizes final render"
      slug:
        required: false
        label: "lowercase ASCII letter then letters/digits/hyphens, 1-48; default tour"
      note:
        required: false
        type: text
---

<Procedure>

1. Use a `specialist_call(kind="work")` session even though media cost is
   free. No URL fetching, capture, automation, generation, uploads or TTS.
   URL-only input returns a request for screenshots from a separately
   authorized capture job; never claim capture is implemented here.
2. Read the selected style: [flat](references/styles/flat.md),
   [glass](references/styles/glass.md), or [outline](references/styles/outline.md).
   Read [steps](references/steps.md) for manifest/clock/OCR limits. Confirm
   that the supplied screens actually show the task ending successfully.
   Repeated clicks on the same screenshot can be legitimate; judge intent,
   not filename uniqueness. Narration is a finished audio-creator WAV plus
   its current `.words.json`, never a text request to synthesize here.
3. Write the filled form as UTF-8 JSON in a job scratch file. `task` and
   `app` live there only, not in the steps manifest. Text travels via file,
   not Japanese argv. Use absolute physical paths (no symlinks, URLs or
   shell interpolation). Dependencies: Python with Pillow, ffmpeg/ffprobe,
   installed HyperFrames CLI; Tesseract only for text anchors. The bundled
   GSAP core retains its own license/provenance; no external runtime skills.
   Missing dependencies return a gap; do not install packages automatically.
4. Run the leaf-owned deterministic helper, in its own terminal command:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/tour.py scaffold --form <form.json> --project <deliver>/tour-project
   python3 ${HERMES_SKILL_DIR}/scripts/tour.py snapshot --project <deliver>/tour-project --out <deliver>/tour-preview
   ```

   The parent delivery directory must already exist. All project, preview
   and final child directories must be new. Preserve failed outputs and
   evidence; retry into a new child, never clear a directory. The helper
   copies original inputs, normalizes static images and freezes hashes.
   Never edit generated HTML, timing or vendor code at runtime.
5. With `preview: yes`, stop after snapshots and QA. Return the preview
   path and the next handoff: `intent: revise <preview directory>`, same
   form with `preview: no`, approving this exact project. For an unchanged
   approved preview, reuse its project without scaffolding or modifying
   its saved form (the saved form still says yes):

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/tour.py render --project <deliver>/tour-project --approved-preview <deliver>/tour-preview --out <deliver>/tour-final
   ```

   `--approved-preview` is used only after actual client approval, not
   self-approval. Changed fields require a new project and preview; keep
   the old version. With initial `preview: no`, still snapshot/check first,
   then render without `--approved-preview`. The helper verifies frozen
   project hashes on every operation and fully decodes the MP4.
6. Long commands use `background: true` and polling under the actual tool
   timeout. Inspect per-step snapshots and final decoded review frames;
   append findings to `qa.md` before the next look. Never call remote video
   analysis under this form. Do not claim that local samples verify all
   temporal behavior or that WAV hash matching means speech was heard.

</Procedure>

<QA>

- Bounds: 1-15 steps plus done; total including goal/narration <=60 s;
  1280x720 or 720x1280 at 30 fps. Screens share pixel dimensions, are static
  PNG/JPEG/WebP, <=16M pixels and <=8192 per side. Targets stay within them.
- Run evidence includes real rendered frames, not HTML inspection alone.
  Check every target, cursor tip or mobile tap ring, typed value, final
  done state and frame edges. `auto` does not infer the actual OS.
- Read runtime/layout/contrast findings from `check.json`. Its contrast
  samples measure authored text, not the screenshot's raster UI text.
  A skipped audit or zero text checks is unverified, never a pass. Check
  screenshot UI readability visually at native size and disclose blur or
  insufficient screenshot resolution. Glass blur applies only to backdrop.
- Final QA: measured codec/dimensions/duration/audio presence/bytes and full
  decode from `qa.json`; compare preview to final review frames. SRT timing
  from speech is estimated. Pacing, audio quality and sync remain unverified
  unless actually inspected; never use white pixels as proof of a cursor.
- Bound the visual review to one per-step pass plus one corrective pass.
  Report failures rather than iterating indefinitely or relaxing bounds.

</QA>

<Report>

`create-tour`; project/preview/final paths as applicable; RESULT JSON;
frame/style/background/backdrop; QA evidence and verdict per check;
unverified temporal/audio/UI-text checks; `spend: media generation 0`;
questions or exact approval/revision handoff for Creator. A preview is not
an MP4 delivery. Synthetic fixtures are test evidence, never product-live
or two-client handoff evidence.

</Report>
