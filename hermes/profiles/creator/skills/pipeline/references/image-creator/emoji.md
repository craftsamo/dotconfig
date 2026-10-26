# image-creator: emoji

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-emoji` — text emoji: one to three lines of bold text in a colour on transparency or a rounded tile, finished per platform as a set.
- `generate-emoji` — a pack of one character (from a reference photo, a mascot, or a description) drawn by an image model in a named style across a set of expressions.
- `edit-emoji` — crops a face from a photo into a circle or rounded square, cuts a subject out, adds an outline, re-finishes a pack for another platform; nothing redrawn.
- `analyze-emoji` — findings on a file or pack: platform size/format/byte limits, readability at 32 px, one character across the set, light and dark backgrounds.

## Range

- Platforms: slack, discord, telegram, telegram-emoji, line, generic; one set per platform, with a sheet.
- Text emoji are deterministic and use a Japanese-capable font; no model draws them.
- Character packs are two rounds: character sheet candidates first, then the pack on the chosen anchor. Pack kinds: expressions, gaming, love-hype, meme-classics, custom (own item list).
- Drawn styles: chibi-cartoon, kawaii-pastel, pixel, flat-sticker, clay, crayon, sumi-ink, origami, neon, or a described one. A real person's photo as `reference` needs consent for the upload.

## Where directions go

- `style` carries the look; one file per option under `references/styles/` of `generate-emoji`, e.g. `skill_view(name="generate-emoji", file_path="references/styles/pixel.md")`. Pack contents live under its `references/packs/`.
- `pack`, `items`, `palette`, `stroke`, `platform` shape a character pack; `items`, `color`, `tile`, `outline` shape text emoji; `note` takes the rest.

## Boundaries

- A brand character that does not exist yet comes first: [mascot](mascot.md); its approved anchor becomes the emoji reference.
- One standalone picture of a photo's subject: [reimagine](reimagine.md). A single icon: [icon](icon.md).

## Examples

No stored example; propose the leaf's representative sample unit: the anchor round, a character sheet of the character in the chosen style, before any pack (for text emoji, a few items on one platform).
