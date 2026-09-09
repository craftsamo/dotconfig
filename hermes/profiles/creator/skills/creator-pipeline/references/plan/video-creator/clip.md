# Plan — video-creator: clip

Read [common plan](../index.md) first.

## Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for clip: 2 variant attempts + 1 corrective total, including failed
video_generate invocations.

## A photo that leaves the machine

For clip, load the form rather than borrowing image defaults. Ask for the
subject/use, one motion/camera direction and a style; aspect defaults to
16:9 and duration to 5 seconds. A native still to animate is `source`,
appearance guidance is `reference` (one image). Both require
`upload_inputs: yes` before generation. `remote_analysis: yes|no` is a
separate decision for generated or supplied video: yes uploads the clip
to the configured analysis provider; no leaves temporal/audio QA
unverified. Ask in the same clarify round, not after production. An
assistant brief must carry that consent or explicitly request remote
analysis; never infer consent from a bare local file path. No TTS happens
inside VideoCreator; tour narration uses completed audio-creator inputs,
and other narration/assembly remain separate legacy jobs.

For edits, destination (landscape/portrait/square/exact size) and fit
(contain/cover) are separate. Default contain avoids losing edges. GIF
loses audio and `loop` only controls GIF playback; do not promise a
seamless animation or silently discard sound. A topic/audience explainer
now has a served route ([create-explainer-video](explainer-video.md));
requested work still outside every served contract (multi-shot montage, ComfyUI,
pixel-grid animation, or explicit legacy Manim work)
chooses its existing legacy family up front rather than forcing it into
clip and falling back after failure. An unsupported requested renderer is
a capability finding; never substitute another renderer or legacy workflow.
