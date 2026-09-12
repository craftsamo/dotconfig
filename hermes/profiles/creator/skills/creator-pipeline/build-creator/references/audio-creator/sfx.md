# Build — audio-creator: sfx

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's `generate-sfx` | `kind="work"`; keep job state, variants and packaging/QA in one resident session even though local Medium spends $0. `create-sfx`/`edit-sfx`/`analyze-sfx` are free, bounded one-reply leaves and use the generic `inquiry` row in [common build](../../SKILL.md) |

## Supervising

Like [analyze-speech](speech.md), `analyze-sfx` returns findings only, so
`deliver` may be omitted.

For generate-sfx, relay exactly what was settled: if no engine is named,
audio-creator uses the local Medium default (no paid approval to relay,
still worth stating the requested `seconds`/`seed` if the client cares
about a specific take). If the client explicitly wants
`fal:elevenlabs-sfx-v2`, relay the approved engine/prompt/seconds/loop/attempt-cap/USD
estimate exactly as approved — never let audio-creator's own engine-
availability finding stand in for that approval. Never approve a seed on
fal or a loop/prompt_influence control on local; the leaf rejects both
outright. A finished sfx WAV may later feed `create-ad` as one distinct
placed audio cue or `create-mix` as one of its `sources` — never folded
into a create-tour generation job; a finished Mix may later feed that tour.
