# Commission — video-creator: clip

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| one short silent generated shot, from text or a starting still, in a named/described style | `generate-clip` | metered, 1-15 seconds, 720p request, default 2 variants + 1 corrective; input-upload and remote-analysis consent are distinct |
| trim/fit/mute/re-encode one existing segment as MP4/WebM/GIF | `edit-clip` | free of generation, at most 60 seconds; contain by default; GIF repeat is playback metadata, not seamless motion |
| technical and visual findings on one short clip, no new video | `analyze-clip` | at most 60 seconds; local samples or one consented remote full-clip analysis; timestamps and explicit unverified checks |

Unsupported fields or a failed production are findings for the user, never a silent switch to another method.

## Choosing and filling

### Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for clip: 2 variant attempts + 1 corrective total, including failed
video_generate invocations.

### A photo that leaves the machine

For clip, load the form rather than borrowing image defaults. Ask for the
subject/use, one motion/camera direction and a style; aspect defaults to
16:9 and duration to 5 seconds. A native still to animate is `source`,
appearance guidance is `reference` (one image). Both require
`upload_inputs: yes` before generation. `remote_analysis: yes|no` is a
separate decision for generated or supplied video: yes uploads the clip
to the configured analysis provider; no leaves temporal/audio QA
unverified. Ask in the same question round, not after production. The
handoff must carry that consent or explicitly request remote
analysis; never infer consent from a bare local file path. No TTS happens
inside VideoCreator; tour narration uses completed audio-creator inputs,
joining finished clips under a finished soundtrack is [create-master](master.md),
and other narration/assembly is not served: `no skill fits`.

For edits, destination (landscape/portrait/square/exact size) and fit
(contain/cover) are separate. Default contain avoids losing edges. GIF
loses audio and `loop` only controls GIF playback; do not promise a
seamless animation or silently discard sound. A topic/audience explainer
now has a served route ([create-explainer-video](explainer-video.md));
requested work still outside every served contract (multi-shot montage,
ComfyUI, pixel-grid animation, or explicit Manim work) is not served:
`no skill fits`, decided up front rather than forced into clip and falling
back after failure. An unsupported requested renderer is a capability
finding; never substitute another renderer or workflow.

## Transport

`generate-clip` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [commissioning](../SKILL.md)'s transport
table. `analyze-clip` is free and bounded one-reply: use the generic
`inquiry` row there instead.

## Round-trip and approvals

For analyze-clip, `deliver` may be omitted: its report and scratch evidence
are the result, not a new movie. A free video analysis may approach the
reply window; use `kind="work"` when the estimate exceeds it rather
than repeating a request that may still be running.

For generate-clip, relay `upload_inputs`/`remote_analysis` exactly as
approved and unchanged: the leaf itself asks a question before any
upload when `source`/`reference` is supplied without `upload_inputs: yes`,
and treats a bare local file path as no consent for `remote_analysis`.
Transport is not an additional grant — do not infer consent yourself to
speed up the handoff.
