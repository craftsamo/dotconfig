# Build — audio-creator: music

Read [common build](../index.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's `create-music`/`generate-music`, both rounds | `kind="work"` from the proposal onward; keep the proposal, Creator-relayed approval and production in the same resident conversation even though round A makes no audio call and local generation spends $0. `edit-music`/`analyze-music` use inquiry only when known to finish in one reply; otherwise work |

## Supervising

For `create-music`/`generate-music`, relay round A's handoff with no
`approved_plan`/`approval_sha256` and expect back only a
`proposal-v<N>/proposal.md` path and its SHA-256, zero spend. Relay that exact
proposal and hash to the client for approval; only a matching second
handoff (`intent: revise <previous delivery>`, the same
`approved_plan`+`approval_sha256`) releases a render or `music_generate`
call. A changed creative field needs a new proposal, never a generation
against stale approval text. For `generate-music`, if no engine is
named audio-creator uses the local Medium default (no paid approval to
relay); an explicit `fal:stable-audio-3-medium` request needs the
approved engine/prompt/duration/seed/attempt-cap/USD estimate relayed
exactly as approved, never audio-creator's own `music_engines`
availability finding standing in for that approval. `edit-music`/
`analyze-music` are free, bounded one-reply leaves like `edit-sfx`/
`analyze-sfx` (see [sfx](sfx.md)); `analyze-music`'s `deliver` may
likewise be omitted.
