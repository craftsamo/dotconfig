# Build — video-creator: explainer-video

Read [common build](../index.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-explainer-video` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; the propose/freeze/snapshot/render rounds and any dependency-request round-trip are not one-reply work |

## Supervising

For `create-explainer-video`, keep the propose/freeze/snapshot/render turns
in one specialist work conversation the same way as
[create-tour](tour.md). Relay
`propose`'s `pending-inputs`/`awaiting-approval` result and its proposal
SHA-256 for client approval before anything else; never invent a file or
hash for an input the spec marked pending. A dependency request the hands
return (missing character art, script, grounding, or narration) is a
finding for you to release as its own separately budgeted/approved unit
through image-creator/writer/researcher/audio-creator — never something
VideoCreator fetches itself, and never a reason to relax framing/
performance/lip_sync to something less than what was asked. The proposal
also fixes an explicit v1 HyperFrames or v2 Motion Canvas renderer; changing
it needs a new proposal too, never a silent switch, and an old v1 Motion
Canvas discussion-only proposal cannot be resumed as a render — only a
fresh v2 proposal and approval can. Only a
matching `approved_plan`+`approval_sha256` releases `freeze`, and only a
matching `approved_preview`+`approval_sha256` releases `render`; a changed
topic/audience/learning_goal or framing/performance/lip_sync choice needs
a new proposal, never a render against stale approval text. Never resolve
or relay the caller's private asset root/name in the handoff text beyond
what the leaf's form actually needs.
