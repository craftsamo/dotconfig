---
name: generate-clip
description: >-
  Generate one short, silent, single-shot video from a subject and motion
  direction, optionally animating a supplied image. 1-15 seconds, 720p
  request, named or described style; default 2 variants + 1 corrective.
  Not a narrated film, montage, exact lip-sync, pixel-perfect sprite loop,
  or a deterministic animation of a logo. Existing edits use edit-clip.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: metered
    output: "clip_<slug>_v<N>.mp4, poster_<slug>_v<N>.png, prompt.txt, raw originals and qa.md"
    form:
      what_for:
        required: true
        label: "subject, setting and intended use in one sentence"
        example: "A small ceramic robot on a desk, a silent website hero"
      motion:
        required: true
        label: "one visible action and camera instruction, not a multi-scene storyboard"
        example: "The robot turns its head toward camera; camera stays fixed"
      style:
        required: true
        options: [cinematic, flat-animation, clay, pixel]
        other: true
        label: "a listed style or a described look; pixel is an aesthetic, not guaranteed grid-correct sprite animation"
      source:
        required: false
        type: image
        label: "local starting still to animate through image_url; requires upload consent"
      reference:
        required: false
        type: image
        label: "one local appearance reference via reference_image_urls; not the starting frame; requires upload consent"
      aspect:
        required: false
        options: ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"]
        label: "default 16:9; requests outside the backend's current surface are blocked before spend"
      duration:
        required: false
        type: int
        label: "1-15 seconds, default 5; backend limits are checked again before spending"
      remote_analysis:
        required: true
        options: ["yes", "no"]
        label: "yes authorizes uploading generated clips to the separate analysis provider; no leaves temporal QA unverified"
      upload_inputs:
        required: false
        options: ["yes", "no"]
        label: "must be yes when source/reference is supplied; authorizes those images leaving the machine for video generation"
      slug:
        required: false
        label: "safe ASCII filename stem; default generated"
      note:
        required: false
        type: text
---

<Procedure>

1. This is metered and runs in a resident session. Check video_generate's
   current schema/provider capabilities before spending: duration, aspect,
   720p, image_url for source and reference_image_urls for reference. Never
   omit supplied images to make an unsupported call succeed. Source or
   reference without `upload_inputs: yes` returns Q<n> before any upload.
   Use only local existing images; this form supports ONE reference, not a
   list (the backend's larger maximum does not change the form type).
2. Load `references/styles/<style>.md`; for other, write an equivalent
   medium/prompt/QA block. Look once at each supplied image and record the
   identity, framing and palette to preserve. Source is the initial image;
   reference is appearance guidance. With source, preserve its composition
   and disclose backend-determined aspect rather than silently cropping.
3. Write `<deliver>/prompt.txt` BEFORE spending: form, style block, prompt,
   budget, input roles and upload consent. Prompt = subject/setting + one
   action + camera + style + no text/watermark + silent. Unless an entrance
   or exit was asked for, keep the entire subject in frame from first to
   last frame; do not begin halfway off-screen. Japanese text goes
   through files/tool arguments, never a shell argv prompt. This is a
   generated shot, not a guarantee of exact physical behavior.
4. Call `video_generate(prompt=..., duration=..., aspect_ratio=...,
   resolution="720p", image_url=<source if supplied>,
   reference_image_urls=[<reference if supplied>])` once per variant.
   Optional schema fields are passed only when advertised. Do not set a
   model or seed the backend did not offer. Record provider/model/seed and
   errors the tool returns. Count each invocation, including failures,
   against the grant; do not retry automatically. The default is TWO
   variant attempts and ONE corrective attempt total, not per variant.
5. Localize every returned file/URL immediately into `<deliver>/raw/`
   using the file/curl tools; record the original result. Never download
   to an existing raw path or put expiring URLs in the final report alone.
   The profile disables xAI persistent public storage; URLs are temporary.
   Do not turn storage on for convenience. On this host curl does not
   support `--clobber-never`: check the new target first, then download with
   `curl --fail --location --retry 0 --output <new-raw-path> <URL>`.
   Finish with:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py edit <raw-local-path> <deliver>/clip_<slug>_v<N>.mp4 --mute
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py frames <output> <deliver>/review-v<N>
   ```

   Commands run separately. Background/poll long encodes; terminal timeout
   is configuration-dependent. Do not resize/upscale to disguise a backend
   resolution mismatch. Deliver silent MP4 even if a fallback produced audio;
   record that removal. Copy review's frame-01.png to poster_<slug>_v<N>.png.
6. Per successful variant: sheet ONCE, native middle frame ONCE, and (only
   with `remote_analysis: yes`) video_analyze ONCE asking for timecoded
   motion/identity/style failures across the WHOLE shot. Above 30 MB make a
   scratch proxy with helper `edit --max-bytes 25000000 --mute`; disclose
   its use. Append each finding to `qa.md` BEFORE the next visual call.
   A failed analysis is a gap, not grounds to generate another take.
7. If both variant attempts leave no passing shot, use at most ONE
   corrective generation for a specific observed defect. Log prompt delta,
   count the attempt, repeat the same bounded QA, then stop. When remote
   analysis is declined/unavailable, report a candidate with temporal QA
   unverified, never claim a fully passing movie from sampled stills.
8. `intent: revise`: inventory prompt/raw/qa first; use surviving outputs
   and ask Creator for the remaining grant if ambiguous. Never reset the
   budget on resume. Produce new filenames only.

</Procedure>

<QA>

- Integrity: actual dimensions, codec, fps, duration, bytes and `decoded`
  from the helper; silent H.264/yuv420p MP4. Compare requested duration
  within max(0.25s, one frame). A different resolution/aspect is a reported
  mismatch, not permission to crop/upscale or pretend the spec was met.
- Subject/style: recognizable subject, source/reference identity retained,
  composition intact, no unwanted text/watermark; named style's QA cues.
- Motion: requested subject/camera action, no unintended cuts, flicker,
  geometry drift or morphing; timestamp findings and source (sample/model).
  Only full-clip analysis can support temporal findings, not a poster alone.
- Budget/provenance: each invocation recorded including failure, raw files
  retained, no silent backend/model claim, analysis calls <= successful
  variants, input uploads consented. Fallback may have more than one
  provider attempt per tool call; the tally is tool calls, not a dollar cap.

</QA>

<Report>

`generate-clip` + style; prompt/raw/output/poster/qa paths; per variant
RESULT facts and QA verdict (including failed/unverified); exactly one
recommended candidate if any; `spend: video_generate <attempts>/<grant>;
video_analyze <calls>`; backend/seed when returned; remaining budget;
questions for Creator. Failed candidates are labeled, never called accepted.

</Report>
