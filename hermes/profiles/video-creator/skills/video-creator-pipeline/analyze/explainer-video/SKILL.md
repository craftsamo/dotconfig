---
name: analyze-explainer-video
description: >-
  Review one existing explainer video (up to 600 seconds) frame by frame for
  on-screen text defects, caption-versus-picture mismatches, text hidden by
  overlaps or too small for a phone, drawing defects in figures and portraits,
  and list its factual claims verbatim. Findings and a claim list only, never
  a new or corrected video. Not speech or listening (audio-creator), not the
  thumbnail (analyze-card), not likeness, not a fact-check verdict.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "findings table and claim list in the reply; findings.md, claims.md and local evidence retained under deliver when given, never a new video"
    form:
      source:
        required: true
        type: file
        label: "one local explainer video, at most 600 seconds; a longer one is refused, not sampled"
      captions:
        required: false
        type: file
        label: "timed caption file, one `[m:ss] text` line each; absent = caption-versus-picture unverified"
      focus:
        required: false
        type: text
        label: "extra checks or known recurring defects to look for, e.g. a portrait drawing check; never a likeness verdict"
      remote_analysis:
        required: true
        options: ["yes", "no"]
        label: "yes permits one upload of this video for temporal analysis (possible only at <=30 MB or <=60 s); no keeps it local (stills only)"
      note:
        required: false
        type: text
---

<Procedure>

1. Use a new job directory: `<deliver>/review-<n>` when `deliver:` is given,
   else a new scratch directory. Never modify the source, reuse another job's
   evidence or write into skills. Record the source path and its probe.
   Keep `findings.md` and `claims.md` in the job directory from the start and
   append to them before every next visual call; a stopped run still leaves
   what it saw.
2. Build the overview locally:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/explainer-evidence.py overview <source> <job>/overview
   ```

   It writes 1 fps stills, 0.5 s stills around each detected cut (at most 40
   cuts get them; more are thinned evenly and listed in `evidence.json`), 3x3
   contact sheets with the time bottom-right, and `evidence.json`. A source
   over five minutes may outlast a foreground command: run it in the
   background and wait for its completion. Read every sheet once, in order,
   at most two images per turn. With `captions`, read the caption file once
   and compare each line with the picture at its time.
3. Go closer only where a sheet shows a candidate, each look a new output
   directory. A native frame, or an enlarged region of it:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/explainer-evidence.py detail <source> <job>/detail-<n> --at <seconds> --crop <x0> <y0> <x1> <y1>
   ```

   Anything moving — a counter, a highlight, a label entering — gets a
   0.3 s window (at most 4 s) before it is called a mismatch:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/explainer-evidence.py window <source> <job>/window-<n> --start <seconds> --duration 2
   ```

   A text height is measured on a native frame (never a crop), reported at
   1080p; add `--ink dark` for dark text on a light ground. Never ask vision
   for pixel sizes:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/explainer-evidence.py measure <job>/detail-<n>/<frame>.png --box <x0> <y0> <x1> <y1>
   ```
4. Check, per moment:
   - text: typos, missing or broken glyphs, text cut off by the frame,
     on-screen text that contradicts the caption at that time, text too small
     for a phone (under about 30 px at 1080p, measured);
   - overlap: keep it only when it hides text, a value, a unit, a chart point
     or part of a figure. A label resting on a character while every word
     stays legible is staging, not a finding;
   - figures and portraits: a name, title or year that disagrees with the
     captions, a visibly broken drawing. A flat-coloured limb over
     same-coloured clothing is hidden, not missing. Never say whether a
     portrait looks like a real person, and never identify anyone from a face;
   - claims: every factual statement (figures, dates, ranks, causes, quotes
     of people) on screen or in the captions, verbatim with its time and
     where it appears. List them; do not judge them.
   Apply `focus` on top. A long stretch of one caption line over logos with
   no diagram is a finding only when `focus` asks for pacing.
5. `remote_analysis: no` means no upload: motion between stills, audio and
   exact cut times stay unverified. With yes, ONE `video_analyze` call with
   focused temporal questions and a request for timestamps, on the source
   itself when it is at most 30,000,000 bytes, or on a proxy made with the
   pipeline helper when the source is at most 60 seconds:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py edit <source> <job>/proxy.mp4 --max-bytes 25000000
   ```

   A source that is both larger and longer has no upload path: report
   "remote analysis not run (size and length)" under unverified, never trim
   it to fit. A failed call is a gap, never a retry loop.
6. Write the two files in the client's language, one line per item:

   ```text
   findings.md:  m:ss | text|content|portrait | problem, quoting on-screen words verbatim in quotation marks | evidence path | certain|confirm
   claims.md:    m:ss | caption|screen | the claim, verbatim
   ```

   Exactly five cells per finding line, no `|` inside a cell; evidence paths
   relative to the job directory. A finding with no single time writes `-`.

   `certain` only for what a native frame or a measurement shows;
   anything that rests on taste, listening or outside facts is `confirm`.

</Procedure>

<QA>

- Every finding cites a native frame, crop, window sheet or measurement from
  this job; a contact-sheet tile alone is not enough for `certain`.
- Coverage is the 1 fps stills plus the cut stills; say so, and name any
  stretch not inspected. Stills are not continuous playback.
- Text heights come from `measure`, not estimates.
- No likeness, identity, listening, speech or fact verdicts; claims are
  listed, never rated. No thumbnail review: that is the thumbnail leaf's.
- At most one cloud video analysis; no source writes, no new or repaired
  video, no media generation.

</QA>

<Report>

`analyze-explainer-video`; source and probe; coverage (stills, cuts, windows
looked at, blind spots); findings table `m:ss | aspect | problem | evidence |
certain/confirm`, certain first; claim list; unverified items (audio, motion
between stills, anything outside `focus`); job directory with `findings.md`,
`claims.md` and evidence; `spend: media generation 0; video analysis <0|1>
calls`. A suggested fix is not permission to edit or generate.

</Report>
