# Commission — audio-creator: sfx

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a deterministic short UI/game sound from a closed set of eight local kernels (click, beep, chime, whoosh, riser, pop, ui-tick, noise-burst) | `create-sfx` | free, zero model, no network call; a described real-world sound routes to generate-sfx instead |
| a described real-world or complex sound effect, default engine | `generate-sfx` (local Stable Audio 3 Medium, engine omitted) | free ($0), no paid approval needed; takes a seed (default 0), rejects loop/prompt_influence outright; still bounded by an attempt cap (default 3 variants + 1 corrective, hard cap 8) |
| the same, via the explicitly chosen paid engine (loop or prompt-adherence control needed) | `generate-sfx` (`engine: fal:elevenlabs-sfx-v2`) | metered; explicit current-work paid approval of engine/prompt/seconds/loop/attempt cap (default 3 variants + 1 corrective) and a USD estimate before any spend; no seed, no local fallback |
| trim / pitch shift / reverse / pad / fade / true-peak normalize / format-convert of an existing SFX file | `edit-sfx` | free; preserves the original, never re-synthesizes |
| findings on an existing SFX file's format, loudness, clipping and silence | `analyze-sfx` | free; measured findings only, never a listening verdict; deliver may be omitted |

## Choosing and filling

### Budget

`generate-sfx` defaults to the local Stable Audio 3 Medium engine: $0
spend, no paid approval needed. The explicit `fal:elevenlabs-sfx-v2`
alternative proposes 3 variants + 1 corrective by default (a proposal,
not a spend grant) and needs its own explicit current-work paid approval
and USD estimate before any call, never a default budget.
`create-sfx`/`edit-sfx`/`analyze-sfx` spend no takes at all. For another
subject, read that subject's reference and hands leaf for its
allowance.

### Short SFX, not a described score

A closed set of eight local kernels (click, beep, chime, whoosh, riser,
pop, ui-tick, noise-burst) is `create-sfx`: free, zero model, no network
call — fill `kind`/`seconds`/`pitch` from what the user actually asked,
never approximate a real-world sound with the nearest kernel. Anything
else described (a door creak, a crowd cheer, an engine start) is
`generate-sfx`. It defaults to the installed local Stable Audio 3 Medium
engine (`engine` omitted): $0 spend, no paid approval needed, and it
takes a `seed` (default 0, audio-creator reports the actual seed used per
attempt) — but it rejects `loop`/`prompt_influence` outright, so a
user asking for either gets a question offering the fal alternative, not a
silently dropped control. Choosing the paid `fal:elevenlabs-sfx-v2`
engine instead is always explicit, never picked because local seemed
slow or the user merely prefers it: before any call it needs the exact
`sound` text, `seconds`, `loop`, the attempt cap and a USD estimate at the
published per-second rate settled with the user, the same way a metered
image/video leaf is gated — and it takes no `seed` at all, so a request
for a reproducible fal take is also a question to the user, never silently
dropped or rerouted to local without asking. Neither engine ever substitutes
for the other silently.
`edit-sfx` changes an existing file (trim/pitch/reverse/pad/fade/
normalize/convert) and is never a substitute for a fresh generate-sfx
take; a defect in an existing SFX is a `revise` on the leaf that made it,
not a re-roll disguised as an edit.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's `generate-sfx` | `kind="work"`; keep job state, variants and packaging/QA in one resident session even though local Medium spends $0. `create-sfx`/`edit-sfx`/`analyze-sfx` are free, bounded one-reply leaves and use the generic `inquiry` row in [commissioning](../SKILL.md) |

## Round-trip and approvals

Like [analyze-speech](speech.md), `analyze-sfx` returns findings only, so
`deliver` may be omitted.

For generate-sfx, relay exactly what was settled: if no engine is named,
audio-creator uses the local Medium default (no paid approval to relay,
still worth stating the requested `seconds`/`seed` if the user cares
about a specific take). If the user explicitly wants
`fal:elevenlabs-sfx-v2`, relay the approved engine/prompt/seconds/loop/attempt-cap/USD
estimate exactly as approved — never let audio-creator's own engine-
availability finding stand in for that approval. Never approve a seed on
fal or a loop/prompt_influence control on local; the leaf rejects both
outright. A finished sfx WAV may later feed `create-ad` as one distinct
placed audio cue or `create-mix` as one of its `sources` — never folded
into a create-tour generation job; a finished Mix may later feed that tour.
