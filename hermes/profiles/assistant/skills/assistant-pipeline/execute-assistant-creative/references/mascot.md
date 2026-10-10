# Commission — image-creator: mascot

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a mascot character designed from a concept (a brand's / product's / team's; species, personality, features, palette) in a style (game-2d, chibi, anime-2d, retro-cartoon, flat-vector, painterly, pixel, clay, low-poly, toon-3d, crayon, …), full body, transparent / chroma-key / flat | `generate-mascot` | metered, TWO rounds: without `anchor` it draws 3 full-body concepts + a silhouette sheet and stops; the user approves one, then `intent: revise` + `anchor:` + `pack:` (turnaround 4 / poses 8 / custom) draws the pack on it (default concept 3 + 1/item + ceil(n/4) correctives). The approved anchor is the `reference:` every later asset of the character takes — `generate-emoji`, stickers, video |
| a delivered mascot re-keyed for video (chroma key), cropped to a head / bust avatar, resized, outlined, re-cut | `edit-mascot` | free; never recolours — a shaded character is redrawn, not recoloured |
| findings on a mascot file, a concept round or a pack (square, cut-out, silhouette, 64 px read, light / dark, measured palette vs asked, identity vs anchor), no file | `analyze-mascot` | free |
| a mascot from a stock library, or one drawn from a first-party SVG | — | there is no source-mascot or create-mascot on purpose: a mascot is designed, not fetched, and a first-party mark becomes an icon set (`create-icon`), not a character |

## Choosing and filling

### Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for mascot: 3 concepts, then 1 per item + ceil(items/4) correctives. For
another subject, read that subject's reference and hands leaf for its
allowance.

### Two-round leaves — mascot-specific

`generate-mascot` follows the shared two-round gate — see
[emoji](emoji.md) "Two-round leaves — the shared gate" for the full
refuse-to-draw-on-an-unapproved-likeness mechanics, the `revise <dir>` +
`anchor:` handoff, and the `passed: false` corrective-budget decision,
which apply here unchanged. For a mascot the second round also needs
`pack:` (`turnaround` for a model sheet, `poses` for the everyday eight,
`custom` + `items`); a user who only wanted the character stops after
round A — the concept IS the deliverable.

### A character lives once

A character lives once: an approved mascot anchor is the `reference:`
for its emoji pack (`generate-emoji` — see [emoji](emoji.md)), and a
mascot the user wants for video goes through `edit-mascot` with
`background: chromakey` rather than a second generation. When the user
asks for "an emoji of our mascot" and no mascot exists yet, that is two
forms in order — `generate-mascot` first, `generate-emoji` on its
anchor second — and you say so.

## Transport

`generate-mascot` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [commissioning](../SKILL.md)'s transport
table, the same two-round shape as [emoji](emoji.md). `edit-mascot` and
`analyze-mascot` are free and bounded one-reply: use the generic `inquiry`
row there instead.

## Round-trip and approvals

The round A / round B relay (candidates and stop, then the exact `revise
<dir>` + `anchor:` line, the corrective budget, and a `passed: false` item
going back to the user rather than being decided locally) is the shared
gate — see [emoji](emoji.md) "The shared two-round relay" for the
full mechanics. Round B additionally carries `pack:`
(`turnaround`/`poses`/`custom` + `items`) exactly as the user chose; a
user who only wanted the character stops after round A, so do not send a
round B handoff the user never asked for. The approved anchor is a durable
identity: relay it unchanged as the `reference:` for a later `generate-emoji`
form on the same character, and for `edit-mascot`'s `background: chromakey`
request rather than opening a second generation.
