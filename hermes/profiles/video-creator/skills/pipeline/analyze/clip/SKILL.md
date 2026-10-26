---
name: analyze-clip
description: >-
  Inspect one local short video (up to 60 seconds) for technical format,
  framing, motion continuity, artifacts and suitability for its intended
  use. Return findings with timestamps, not a new video. Not generation,
  editing, a full-length film review, or a factual claim about depicted events.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "findings table in the reply; deliver may be omitted; scratch evidence only"
    form:
      source:
        required: true
        type: file
        label: "one local video, at most 60 seconds; use edit-clip to select a longer source's segment"
      what_for:
        required: false
        options: [social-post, loop, hero, ad]
        other: true
        label: "intended use or specific question; absent = general technical/visual review"
      against:
        required: false
        type: image
        label: "optional still image whose subject or style must be preserved, not a second movie"
      remote_analysis:
        required: true
        options: ["yes", "no"]
        label: "yes authorizes video upload to the configured analysis provider; no gives local measurements and sampled-still review only"
      note:
        required: false
        type: text
---

<Procedure>

1. Create a new scratch directory with `mktemp -d`; never reuse another
   job's frames or write into the skill tree. Probe the source:
   `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py probe <source>`.
   Above 60 seconds, ask for a segment instead of silently watching only
   the opening. Keep `RESULT:` and each finding in scratch `qa.md`.
2. Run `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py frames <source> <scratch>/review`.
   Inspect the sheet once, the native middle frame once, and `against`
   once if provided. Append the finding before each subsequent look.
   For `what_for: loop`, look at first/last frames instead of the middle
   and state that stills alone cannot prove a seamless velocity boundary.
3. When `remote_analysis: no`, do not upload the movie. Report temporal
   and audio checks as unverified; never silently substitute cloud review.
   When yes, prepare the analysis input BEFORE calling the tool. The plugin
   limit applies to base64, not raw video bytes. If source is
   above 30,000,000 bytes, make a scratch proxy with the helper's `edit`
   command, `--max-bytes 25000000`, same aspect and audio. This is a
   two-pass encode; run in background when it may outlive the terminal
   timeout. Measure/inspect the ORIGINAL; temporal review uses the proxy.
   Disclose the proxy and compression limitation. Never trim away content
   to fit the analysis cap. A failed proxy is a reported gap, not permission
   to send the oversized original.
4. Only with yes and a correctly sized analysis input, call
   `video_analyze(video_url=<original or proxy path>, question=<focused
   question covering motion, artifacts, scene changes, audio if present,
   and intended use; request timestamps>)` ONCE. This uploads the file to
   the configured MiMo backend; free means no media generation, not free API.
   A failed call is a reported gap, not a retry loop or a passing check.

</Procedure>

<QA>

- Technical facts come from ffprobe, not the model: dimensions, display
  rotation/SAR, fps, duration, bytes, codec and audio presence.
- Visual findings cite sample timestamps from frames.json. Compare the
  requested identity/style explicitly when against is provided.
- Temporal findings cite the video-analysis timestamps and distinguish
  model observations from measured facts. Do not infer sound quality from
  an audio stream's mere presence. Note unavailable analysis or uncertain
  observations, and avoid claims of exhaustive per-frame verification.
- Privacy/budget: no remote call without yes; at most one video_analyze,
  no video_generate and no repaired media delivered.

</QA>

<Report>

`analyze-clip`; source; measured facts; table `check | timestamp/file |
evidence | pass/fail/unverified | suggested fix`; overall verdict and
coverage limits; scratch evidence path; `spend: media generation 0;
video analysis <0|1> calls`. No new video. A proposed fix is not permission
to edit or generate.

</Report>
