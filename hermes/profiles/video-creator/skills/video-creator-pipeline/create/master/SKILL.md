---
name: create-master
description: >-
  Create one finished delivery master from already-approved parts: silent
  video segments joined in order (cut or dissolve), a finished soundtrack
  (WAV or audio-creator Mix bundle) laid under them, and optional captions
  burned in plus an SRT sidecar. Deterministic and local; decides nothing
  creative. Not trimming/reframing one clip (edit-clip), mixing audio
  (create-mix), authored motion or generated footage.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "master_<slug>.mp4 + optional master_<slug>.srt + sheet.png, join-<k>.png, master.json, qa.md"
    form:
      segments: {required: true, type: text, label: "comma list of local videos in play order; same size and fps"}
      transition: {required: false, options: [cut, dissolve], label: "between segments; default cut"}
      transition_seconds: {required: false, type: text, label: "dissolve length 0.1..2; default 0.5"}
      audio: {required: false, type: file, label: "finished WAV of the exact total length; absent = silent"}
      mix_bundle: {required: false, type: path, label: "audio-creator Mix bundle dir instead of audio"}
      captions: {required: false, type: file, label: "SRT or Mix captions.json; default: the bundle's captions"}
      burn_captions: {required: false, options: ["yes", "no"], label: "yes (default with captions) draws them in; no = SRT only"}
      caption_position: {required: false, options: [bottom, top], label: "default bottom"}
      slug: {required: false, label: "safe ASCII filename stem; default master"}
      note: {required: false, type: text}
---

<Procedure>

1. Work only in `specialist_call(kind="work")`; joins and caption renders
   can outlast one reply window. Every part is already approved: this leaf joins them exactly as the form says
   and decides nothing creative. It never trims, reorders, retimes, crops,
   grades, speeds up, loops, pads or rewrites a part or a caption. A missing
   or ambiguous decision (order, transition, which audio) is one batched
   `Q<n>:` to Creator, never a local choice.
2. Probe each segment with
   `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py probe <file>`.
   Segments must be 8-bit SDR, share size and frame rate and carry square
   pixels without rotation; a mismatch is a dependency request for `edit-clip` (fit or
   re-encode that segment), never an automatic scale. Embedded segment
   sound is dropped; a soundtrack comes only from `audio` or `mix_bundle`.
3. The soundtrack must already last the joined picture's length (within
   one frame). A mismatch goes back to Creator for audio-creator
   (`edit-music` / `edit-mix`); it is never cut, padded or stretched here.
   A dissolve shortens the picture by its length at every join, so state
   the resulting total in the question.
4. Build into a new directory. Use the Hermes venv Python (a Mix bundle is
   verified by AudioCreator's own helper) and run the script in its own
   terminal command, `background: true` for anything long:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python ${HERMES_SKILL_DIR}/scripts/master.py build \
     --segments <a.mp4>,<b.mp4> --out <deliver>/master-v<N> --slug <slug> \
     [--transition cut|dissolve] [--transition-seconds S] [--audio <track.wav> | --mix-bundle <dir>] \
     [--captions <file>] [--burn-captions yes|no] [--caption-position bottom|top]
   ```

   The picture is joined with ffmpeg; burned-in captions are rendered by the
   installed `hyperframes` CLI as a transparent layer over it, one fixed
   readable style. The helper checks canvas, fps, duration, audio presence,
   full decode and true peak (a Mix master against its approved ceiling),
   then publishes the directory; a FAIL publishes nothing. A missing
   `hyperframes` CLI blocks burned-in captions only: report it and offer
   `burn_captions: no`, never a different renderer.
5. Look at `sheet.png`, then each `join-<k>.png` (before, at, after the
   join), at most three images per step, writing each finding to `qa.md`
   before the next look. With burned captions, also check a frame inside
   the longest caption at native size.
6. `intent: revise` builds again from the original parts into a new
   `master-v<N+1>`; never re-encode a previous master.

</Procedure>

<QA>

- Order and joins: segments appear in the given order; every join sheet
  shows the requested cut or dissolve with no black or frozen frame.
- Captions: text verbatim from the file, readable at native size, inside
  the frame, not over a burned-in title of the picture; SRT matches.
- Technical: helper PASS on canvas, fps, duration, audio presence, full
  decode and true peak; `segment_audio_dropped` reported.
- Limits: sampled sheets are not whole-video review; sync, listening and
  caption reading speed stay `unverified`.

</QA>

<Report>

`create-master`; output directory, movie and SRT paths, the RESULT JSON
(inputs with hashes, probe, checks, loudness), the looks taken and
findings, dropped segment sound, any question for Creator, and
`spend: media generation 0`.

</Report>
