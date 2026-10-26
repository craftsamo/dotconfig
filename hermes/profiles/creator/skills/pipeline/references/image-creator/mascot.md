# image-creator: mascot

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-mascot` — a brand, product or team mascot designed from a concept in a named style and the client's palette, cut out on a transparent, chroma-key or flat background; a pack on the chosen character.
- `edit-mascot` — swaps the background (transparent, chroma-key for video, flat), re-cuts a subject, crops to bust or head for an avatar, resizes, adds an outline; nothing redrawn or recoloured.
- `analyze-mascot` — findings on a mascot file, concept round or pack: clean cutout, silhouette, 64 px legibility, light and dark pages, palette match, one character across items.

## Range

- Two rounds: three full-body concept candidates (with a silhouette sheet) first; then a pack on the chosen anchor. A client who only wants the character can stop after round one.
- Pack kinds: turnaround, poses, custom (own item list). Framing: full-body, bust, head.
- Drawn styles: game-2d, chibi, anime-2d, retro-cartoon, flat-vector, painterly, pixel, clay, low-poly, toon-3d, crayon, or a described one. `anime-2d` is the TV-anime cel look; its anchor and poses can serve as the cast of an `anime-2d` story.
- The approved anchor is the reference for every later asset of the character (emoji pack, sticker, video). A shaded character cannot be recoloured deterministically.

## Where directions go

- `style` carries the look; one file per option under `references/styles/` of `generate-mascot`, e.g. `skill_view(name="generate-mascot", file_path="references/styles/chibi.md")`. Pack contents live under its `references/packs/`.
- `concept`, `palette`, `background`, `framing`, `reference`, `pack`, `items` carry the rest; `note` takes anything else. A reference photo of a real person needs consent for the upload.

## Boundaries

- An emoji pack of the character: [emoji](emoji.md), on the approved anchor. A mascot in video: take the chroma-key cutout, then [story](../video-creator/story.md) or [promotion](../video-creator/promotion.md).
- A photo restyled with its own subject: [reimagine](reimagine.md). A game asset set: [kit](kit.md).

## Examples

No stored example; propose the leaf's representative sample unit: the anchor round, three full-body concept candidates in one style and palette.
