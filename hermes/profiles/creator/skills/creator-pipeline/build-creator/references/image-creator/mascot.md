# Build — image-creator: mascot

Read [common build](../../SKILL.md) first.

## Transport

`generate-mascot` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [common build](../../SKILL.md)'s transport
table, the same two-round shape as [emoji](emoji.md). `edit-mascot` and
`analyze-mascot` are free and bounded one-reply: use the generic `inquiry`
row there instead.

## Supervising

The round A / round B relay (candidates and stop, then the exact `revise
<dir>` + `anchor:` line, the corrective budget, and a `passed: false` item
going back to the client rather than being decided locally) is the shared
gate — see [emoji](emoji.md) "Supervising — the shared two-round relay" for
the full mechanics. Round B additionally carries `pack:`
(`turnaround`/`poses`/`custom` + `items`) exactly as the client chose; a
client who only wanted the character stops after round A, so do not send a
round B handoff the client never asked for. The approved anchor is a durable
identity: relay it unchanged as the `reference:` for a later `generate-emoji`
form on the same character, and for `edit-mascot`'s `background: chromakey`
request rather than opening a second generation.
