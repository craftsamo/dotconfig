---
name: edit-clip
description: >-
  Trim, fit, mute or re-encode one existing video segment of at most 60
  seconds as MP4, WebM or GIF without redrawing it. Use for a shorter cut,
  portrait/square export or a byte cap, not montage, captions, generated
  motion or seamless-loop synthesis. No media-generation spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "clip_<slug>.<format> + review frames/frames.json + qa.md; original unchanged"
    form:
      source:
        required: true
        type: file
        label: "local video to edit; select at most 60 seconds with trim if longer"
      destination:
        required: false
        options: [original, landscape, portrait, square]
        other: true
        label: "original (default), landscape 1280x720, portrait 720x1280, square 720x720, or exact WIDTHxHEIGHT"
      fit:
        required: false
        options: [contain, cover]
        label: "contain pads (default); cover crops and requires explicit consent to losing edges"
      trim:
        required: false
        label: "START[:DURATION] in decimal seconds, not hh:mm:ss; e.g. 1.5:6"
      mute:
        required: false
        options: ["yes", "no"]
        label: "no (default) keeps the first audio track; yes removes it; GIF is always silent"
      format:
        required: false
        options: [mp4, webm, gif]
        label: "mp4 (default, H.264), webm (VP9), gif (12 fps unless fps is set)"
      loop:
        required: false
        options: ["yes", "no"]
        label: "GIF playback repeat only, default no; MP4/WebM repeat is a player setting, not a seamless edit"
      fps:
        required: false
        type: int
        label: "1-60; absent preserves timing (GIF defaults to 12)"
      max_bytes:
        required: false
        type: int
        label: "positive hard byte cap; MP4/WebM use two-pass bitrate; GIF only checks the result (reduce size/fps/trim explicitly if over)"
      slug:
        required: false
        label: "safe ASCII filename stem; default edited"
      note:
        required: false
        type: text
---

<Procedure>

1. Probe with `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py probe <source>`.
   Parse `RESULT:` JSON. Validate trim/end, destination and format before
   rendering. MP4/WebM exact dimensions must be even; ask rather than change
   a requested odd dimension. With `original`, one black pixel is padded
   on an odd right/bottom edge, never a content row cropped out. Reject
   unsupported edits (captioning, adding music, object removal) as a gap.
   Use the helper's measurements and `vision_analyze` for the looks below.
   Do not add inline Python, heredocs or ad-hoc pixel scripts for numeric
   padding/source alignment; they trigger terminal approval and are not
   this leaf's checks. If a required tool is blocked, report the gap; do not
   bypass the approval. Write available evidence to qa.md even when blocked.
2. Translate destination into `--size WIDTHxHEIGHT` (omit for original).
   Use `--fit contain` unless cover was explicitly chosen. Translate form
   fields literally to this helper; do not assemble arbitrary filters:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py edit <source> <deliver>/clip_<slug>.<format> --fit <fit> [--size WxH] [--trim START:DURATION] [--format mp4|webm|gif] [--fps N] [--mute] [--loop] [--max-bytes N]
   ```

   Quote paths. Run the script in its own terminal command, not after a
   `cp ... && ...` chain. Long encodes use `background: true` and polling;
   use the actual terminal timeout, never assume 420 seconds is available.
   Original audio is preserved unless mute/GIF is selected; disclose GIF's
   audio loss before the edit. Never overwrite a source or previous take.
3. The helper decodes the entire result and enforces the actual byte cap
   before publishing. If the cap fails, return a question about shortening,
   reducing dimensions/fps or muting; do not change these silently.
   GIF caps are a measured postcondition, not automatic size/fps tuning.
   GIF palette buffering is bounded to 80 million pixel-frames; a larger
   request asks for an explicit smaller size/fps/segment before encoding.
4. Sample the result:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py frames <output> <deliver>/review
   ```

   Look once at `sheet.png` (left to right: timestamps in `frames.json`),
   then once at the native middle frame. For cover, also inspect the same
   original-time source frame to compare cropped edges. The helper uses
   ImageMagick `+append`, not font-dependent `montage`. Append each finding
   to `qa.md` before another look; the visual context holds few images.
5. `intent: revise`: start from the original source, not a lossy previous
   encode, with only the changed fields. Use a new output/review directory.

</Procedure>

<QA>

- Geometry/timing: RESULT dimensions, SAR=1, duration within one frame of
  the selected segment; MP4/WebM yuv420p. Report padding and actual fps.
- Integrity: `decoded: true`, measured bytes <= max_bytes when supplied;
  correct codec/container, first audio track kept or deliberately removed.
- Framing: source subject and text remain readable; contain's bars are
  intentional. Cover can pass numeric tests while cutting a title in half;
  name any lost text/subject as a failure, not a successful fit.
- Review limits: three sample frames do not prove every frame, audio sync
  or smooth motion. This leaf checks the deterministic edit; a temporal
  critique belongs to analyze-clip. GIF repeat metadata proves playback
  repeat only, never a seamless visual boundary.

</QA>

<Report>

`edit-clip`; source and output paths; RESULT JSON; changes made, including
audio loss/padding; QA check/evidence/verdict; review paths and missing
checks; `spend: media generation 0`; any question for Creator. Do not call
a failed framing check a passing delivery.

</Report>
