# Commission — image-creator: kit

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a game props/UI asset kit in one style, including world props, inventory icons, buttons, panels or bars | `generate-kit` | metered; style-sheet approval, then individually generated PNGs. Confirm expanded item/state list and call budget; generated states can drift. Not 3D meshes or web components |
| exact game UI chrome from colours and geometry, including state pairs and 9-slice borders | `create-kit` | free; flat-vector or pixel buttons/panels/bars as SVG + PNG; props and arbitrary art styles go to generate-kit |
| an existing kit cut out, fitted, palette-mapped or packed into a texture atlas | `edit-kit` | free; atlas preserves original pixels; fitting may invalidate pivots and slicing metadata |
| findings on kit consistency, canvases, alpha, state alignment or frame/fill registration | `analyze-kit` | free; no redraw; missing expectations are GAP, not invented PASS |
| existing CC0 game asset packs or a selected subset from Kenney | `source-kit` | free; unknown pack returns search candidates; verified page license + archive provenance, not generated art |

## Choosing and filling

### Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for kit: 3 style sheets, then 1 per item + ceil(items/4) correctives. For
another subject, read that subject's reference and hands leaf for its
allowance.

### A kit is a list, not one image

`generate-kit` follows the two-round gate too — see [emoji](emoji.md)
"Two-round leaves — the shared gate" for the anchor/no-anchor mechanics;
kit's round A produces a style sheet instead of character candidates.
First fill `what_for`, `style`, `contents` and any explicit `items`, and
send a no-anchor form. The hands propose one style sheet containing
representative props/UI per candidate and an expanded item list. Show
the sheet AND list before requesting approval. Round B takes the approved
anchor, list, design lock and explicit image-call allowance; more than 24
items always requires an explicit budget line. Normal/pressed/hover/disabled
each count as an item, not a free variant hidden in the count. Do not
conflate call counts with a verified currency quote.

The listed categories are suggestions, not a closed world or a five-item
cap. Explicit `items` REPLACE defaults. A described category needs agreed
items and canvases before the batch. World props use the chosen camera;
UI faces the screen. `size` in kit forms is an integer scale, not a single
square imposed on every category. Reference images may be uploaded;
confirm authority to send them, do not treat a local path alone as consent.

An AI-generated state pair can differ in silhouette even on the same
anchor. If the user needs exact interchangeable controls, offer
`create-kit` for supported flat-vector/pixel UI; explain its generic
geometry instead of promising a hand-painted reproduction. PNGs that
fail the state check stay flagged, never become a production-ready kit
by removing their failed status. `source-kit` is stock retrieval, with
the pack's own look and license, not a route to redesign it.

## Transport

`generate-kit` is metered and runs in a resident session, the same
two-round shape as [emoji](emoji.md)/[mascot](mascot.md): use the generic
`generate` row (`kind="work"`) in [commissioning](../SKILL.md)'s transport
table. `source-kit`, `create-kit`, `edit-kit` and `analyze-kit` are free and
bounded one-reply: use the generic `inquiry` row there instead.

## Round-trip and approvals

Round A (no anchor) returns a style sheet plus an expanded item list and
stops; show the user both before requesting approval — a sheet alone
is not enough. Round B's `revise <dir>` + `anchor:` carries the approved
style sheet, the approved item list and the design lock unchanged; an item
the user adds or removes after that needs its own count/budget
reconfirmation, not a silent batch against the old total. More than 24
items always needs an explicit `budget:` line before round B. Normal/
pressed/hover/disabled each count as one item in that budget, never a free
variant hidden in the count. A PNG that fails the state check stays flagged
in the manifest — do not relay a kit as production-ready by dropping its
failed status, and offer `create-kit` for exact interchangeable geometry
instead of a second `generate-kit` attempt at the same silhouette match.
