# Build — video-creator: clip

Read [common build](../../SKILL.md) first.

## Transport

`generate-clip` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [common build](../../SKILL.md)'s transport
table. `analyze-clip` is free and bounded one-reply: use the generic
`inquiry` row there instead.

## Supervising

For analyze-clip, `deliver` may be omitted: its report and scratch evidence
are the result, not a new movie. A free video analysis may approach the
reply window; use `kind="work"` when the estimate exceeds it rather
than repeating an A2A request that may still be running.

For generate-clip, relay `upload_inputs`/`remote_analysis` exactly as
approved in Plan and unchanged: the leaf itself returns a `Q<n>:` before any
upload when `source`/`reference` is supplied without `upload_inputs: yes`,
and treats a bare local file path as no consent for `remote_analysis`.
Transport is not an additional grant — do not infer consent yourself to
speed up the handoff.
