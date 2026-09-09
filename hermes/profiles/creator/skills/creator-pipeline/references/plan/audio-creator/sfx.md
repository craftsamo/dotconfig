# Plan — audio-creator: sfx

Read [common plan](../index.md) first.

## Budget

`generate-sfx` defaults to the local Stable Audio 3 Medium engine: $0
spend, no paid approval needed. The explicit `fal:elevenlabs-sfx-v2`
alternative proposes 3 variants + 1 corrective by default (a proposal,
not a spend grant) and needs its own explicit current-work paid approval
and USD estimate before any call, never a default budget.
`create-sfx`/`edit-sfx`/`analyze-sfx` spend no takes at all. For another
subject, read that subject's Plan reference and hands leaf for its
allowance.

## Short SFX, not a described score

A closed set of eight local kernels (click, beep, chime, whoosh, riser,
pop, ui-tick, noise-burst) is `create-sfx`: free, zero model, no network
call — fill `kind`/`seconds`/`pitch` from what the client actually asked,
never approximate a real-world sound with the nearest kernel. Anything
else described (a door creak, a crowd cheer, an engine start) is
`generate-sfx`. It defaults to the installed local Stable Audio 3 Medium
engine (`engine` omitted): $0 spend, no paid approval needed, and it
takes a `seed` (default 0, audio-creator reports the actual seed used per
attempt) — but it rejects `loop`/`prompt_influence` outright, so a
client asking for either is a `Q<n>:` offering the fal alternative, not a
silently dropped control. Choosing the paid `fal:elevenlabs-sfx-v2`
engine instead is always explicit, never picked because local seemed
slow or the client merely prefers it: before any call it needs the exact
`sound` text, `seconds`, `loop`, the attempt cap and a USD estimate at the
published per-second rate settled with the client, the same way a metered
image/video leaf is gated — and it takes no `seed` at all, so a request
for a reproducible fal take is also a `Q<n>:`, never silently dropped or
rerouted to local without asking. Neither engine ever substitutes for the
other silently.
`edit-sfx` changes an existing file (trim/pitch/reverse/pad/fade/
normalize/convert) and is never a substitute for a fresh generate-sfx
take; a defect in an existing SFX is a `revise` on the leaf that made it,
not a re-roll disguised as an edit.
