---
name: analyze-ad
description: >-
  Read one local short advertisement as a creative reference or review its
  message, evidence, typography, pacing and call to action. Produce a
  timestamped breakdown with observations separated from interpretation.
  Use for "how is this ad made?" and "review this ad", even a one-shot ad.
  Technical clip inspection alone belongs to analyze-clip; brand/product
  introductions whose primary goal is understanding rather than an action
  may be PVs. Never infer generation provenance or marketing performance.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "analysis in reply; optional deliver directory retains report.md and local evidence, never a new ad"
    form:
      source:
        required: true
        type: file
        label: "local video, <=60 seconds; never ask for chat attachment when the path is readable"
      purpose:
        required: false
        options: [reference, review]
        label: "reference (default): learn the construction; review: judge against the brief"
      brief:
        required: false
        type: text
        label: "audience, approved message, evidence, CTA and required conditions; unknown criteria stay unknown"
      focus:
        required: false
        type: text
        label: "specific questions; optional"
      remote_analysis:
        required: true
        options: ["yes", "no"]
        label: "yes permits one video upload for analysis; no keeps the video local, not a temporal/audio pass"
      note:
        required: false
        type: text
---

<Procedure>

1. Load [inspection](references/inspection.md). Use a new job directory under
   `deliver:` when supplied; otherwise use a new scratch directory. The main
   result is the reply; persisted `report.md` and evidence are a deliberate
   analyze-ad exception to the older no-file shorthand. Never modify the
   source, reuse another job's evidence or write into skills. Record source
   path/hash and the question. For `review` without a brief, ask only for
   missing criteria that change the verdict; otherwise describe, do not guess.
2. Build the overview locally:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-evidence.py overview <source> <job>/overview
   ```

   This reuses clip-media's probe, keeps native frames, and produces labeled
   contact sheets and `evidence.json`. Default 30 frames, at most 60. A source
   longer than 60 seconds needs an explicit segment, never silently its opening.
   Read each overview sheet once and append observations to `report.md` before
   the next visual call. Reconstruct approximate intervals and name their
   roles: attention, message, support/proof, offer, CTA, brand close. Missing
   roles are observations, not an automatic failure or reason to invent them.
3. Select at most TWO uncertain transition/motion windows from the overview,
   each <=3 seconds and <=16 frames. Explain why each is needed before running:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-evidence.py window <source> <job>/window-1 --start <seconds> --duration 2 --count 8
   ```

   Inspect each sheet once, append the finding. These are sampled positional
   observations, not a complete playback or frame-accurate timing measurement.
4. Read up to THREE native detail frames: important claim, dense/small copy,
   end card/CTA (combine when one frame covers several). Use a fresh output:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-evidence.py detail <source> <job>/detail-1 --at <seconds>
   ```

   Read the native frame, not just the thumbnail. Transcribe exact visible
   words/numbers with timestamps; unreadable text stays unreadable. OCR, if
   used, only nominates text to check visually; it is not truth. In between
   snapshots do not guess exact readable-hold durations. Never ask for an
   upload merely because the source is an MP4; local extraction is the path.
5. `remote_analysis: no` means no video upload. Native image vision follows
   the existing profile policy and is not a promise of fully offline inference.
   Report unobserved audio, continuous motion, sync and exact cut times as
   unverified. With yes, use ONE `video_analyze` call for the remaining focused
   temporal/audio questions, asking for timestamps. If the original exceeds
   30,000,000 bytes, use the pipeline's shared clip-media helper to create a new proxy:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py edit <source> <job>/proxy.mp4 --max-bytes 25000000
   ```

   Retain aspect, entire duration and audio. No
   silent crop/trim/mute, no oversized original on proxy failure. Compression
   is disclosed. A failed call is a gap, never a retry loop. Local cached ASR,
   if already available, may support words only, never listening/music/sync.
6. Write the report in the client's language using the five sections in
   inspection.md. Cite evidence paths and seek times. Distinguish FACT,
   INTERPRETATION, RECOMMENDATION and UNVERIFIED explicitly. Return the report
   and evidence location. No generation, repair, client claim validation or
   automatically triggered create-ad. One review pass; further sampling needs
   a concrete unresolved question and Creator's approval, not "one more look".

</Procedure>

<QA>

- Probe values and source hash are measured; every visible claim quotes a
  native frame. A source ad's numbers/No.1/results are not client-authorized
  copy for a new ad, and not verified facts.
- Sampling covers the opening, middle and last decodable frame. State both
  covered intervals and blind spots. Seek labels are not exact PTS or cuts.
- Separate visual/text evidence from interpretation of audience and intent.
  A missing brief is not a fabricated target, and no conversion uplift is
  inferred from appearance. Do not identify a generating model from pixels.
- Check message hierarchy, mobile-size readability, product identity, claims
  context/qualifiers and CTA. Color/style similarity alone is not good QA.
- Audio-stream existence is not an audio review. Never claim BGM, voiceover,
  speech accuracy, beat sync or listening quality without evidence.
- At most one cloud video analysis, two dense windows and three detail looks;
  no source writes. Frame extraction is not permission to upload.

</QA>

<Report>

`analyze-ad`; source/hash; purpose; measured technical facts; interval table;
Theme/Style/Direction observations; audience/message/proof/CTA interpretation;
severity-ranked issues with `time | evidence | observed/inferred/unverified |
suggested action`; reference-to-production notes; coverage/audio/privacy gaps;
report/evidence paths; `spend: media generation 0; video analysis <0|1> calls`.
Mark unfamiliar marketing claims "present in the source, not fact-checked".
An Ad/PV classification is a routing recommendation, not an industry-wide law.

</Report>
