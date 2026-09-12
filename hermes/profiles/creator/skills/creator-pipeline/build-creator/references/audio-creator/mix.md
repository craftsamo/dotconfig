# Build — audio-creator: mix

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's `create-mix`/`edit-mix`, both rounds | `kind="work"` from the proposal onward, the same two-round shape as `create-music`/`generate-music` (see [music](music.md)); keep the proposal, Creator-relayed approval and render in the same resident conversation. `analyze-mix` is a free, bounded one-reply leaf and uses the generic `inquiry` row in [common build](../../SKILL.md) |

## Supervising

For `create-mix`/`edit-mix`, relay round A's handoff with no
`approved_plan`/`approval_sha256` and expect back only a
`proposal-v<N>/proposal.md` path and its SHA-256, zero renders. Relay
that exact proposal and hash to the client for approval; only a
matching second handoff (`intent: revise <previous delivery>`, the same
`approved_plan`+`approval_sha256`) releases the render. A changed
source, cue placement, gain/fade/envelope, duration or loudness target
needs a new proposal, never a render against stale approval text.
For video work, request `audio_workflow: mix` from create-ad/create-tour
before its formal plan — see
[Ad build](../video-creator/ad.md) and
[Tour build](../video-creator/tour.md)
for the video-side halves of that handoff. Relay the resulting frozen
timing path/hash to AudioCreator; AudioCreator authors gains/ducking, not
the video's required cue times. After Mix approval/render, return
`mix_bundle` to VideoCreator so its normal approvals bind the REAL audio
bytes. No placeholders or pending assets in an approved video plan; no
source-stem double playback.
`analyze-mix` is a free, bounded one-reply leaf like `analyze-sfx`/
`analyze-music` (see [sfx](sfx.md) / [music](music.md)); its `deliver`
may likewise be omitted, and it works on any finished mix file, not only
this pipeline's own deliveries.
