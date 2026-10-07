# image-creator: icon

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-icon` — one icon drawn by an image model in a named or described style, cut out as square PNG variants on a transparent, tiled or flat background.
- `source-icon` — one published glyph fetched from the open Iconify libraries (Lucide, Tabler, Phosphor, Material Symbols, brand marks), as SVG plus PNG; nothing drawn.
- `create-icon` — a favicon / Apple / PWA / maskable set derived from an existing first-party SVG mark; nothing redrawn.
- `edit-icon` — recolours a monochrome mark, swaps or removes its background, cuts a subject out, re-emits at square sizes.
- `analyze-icon` — findings on an icon or set: legibility at small sizes, contrast on light and dark, safe zone, colour count, consistency with a sibling.

## Range

- Always square; `generate-icon` defaults to 1024 px, several variants, one recommended.
- Drawn looks: flat-minimal, glass, pixel, line, clay, origami, isometric, neon, stained-glass, or a described one. It suits a subject or look no library draws.
- Library glyphs and brand marks come in the library's own look, recoloured and placed on a transparent, tile or flat background.
- `source-icon` with `official: yes` delivers a vendor's own logo file unmodified (glyph, lockup or wordmark; the ink for a light or dark background) with its source, hashes and usage terms — or reports that none is distributed.
- Platform sets (favicon sizes, apple-icon, maskable 512) only derive from an SVG that already exists; `generate-icon` does not produce SVG.

## Where directions go

- `style` carries the look; one file per option under `references/styles/` of `generate-icon`, e.g. `skill_view(name="generate-icon", file_path="references/styles/glass.md")`.
- `what_for`, `background`, `tile_color`, `palette`, `reference` (generated) and `color`, `background`, `tile_color` (library / edit) fine-tune; `note` takes the rest.

## Boundaries

- A set for an app is two forms in order: the mark first, then `create-icon` from an SVG; say so instead of promising one step.
- Emoji-sized text pictures: [emoji](emoji.md). A character: [mascot](mascot.md). Many game icons in one language: [kit](kit.md).
- A wide image carrying words: [card](card.md).
- Another company's mark is sourced through the official path, never redrawn, traced or generated; never propose a lookalike. Where none exists, a text wordmark is the user's call and a [card](card.md). The user's own mark is their SVG, taken to `create-icon`.

## Examples

No stored example; propose the leaf's representative sample unit: a single icon in one named style, delivered as variants with one recommended.
