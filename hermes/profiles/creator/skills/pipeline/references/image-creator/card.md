# image-creator: card

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-card` — exact-copy card from approved text and local assets, font-rendered with HTML/CSS (named templates or an authored layout); PNG master, tiles, previews.
- `generate-card` — the same card over a generated text-free backdrop, with exact font-rendered copy; several variants.
- `edit-card` — adapts an existing finished raster card to a destination (cover/contain/pad/focus), optionally adding an exact-text band.
- `analyze-card` — measurements and findings on a card, tile set or panorama against a destination; no new media.

## Range

- Destinations: og, x-post, x-article, x-header, x-pair, x-carousel, instagram, instagram-square, story, youtube-thumb, hero, slide-title, note.
- Tiled panoramas of 3 or 4 tiles (x-carousel), with per-tile headings; x-pair is two candidate crops.
- Looks: thirteen named styles, or a described style taken literally. `create-card` can also author a static layout (`layout_html`), so centering, own typography and extra copy blocks are expressible.
- Copy is always typeset text, never generated lettering. Generated art is only the text-free backdrop (`generate-card`); a supplied background goes to `create-card`.
- Not expressible: generated art with baked-in text, emoji, infographics, slide decks, kanban cards.

## Where directions go

- `style` carries the look; one file per option under `references/styles/` of `generate-card`, e.g. `skill_view(name="generate-card", file_path="references/styles/glass.md")`. `create-card` has its own `references/styles/` and `references/destination/` (one file per destination).
- `destination` picks the canvas; `palette`, `font`, `motif`, `background`, `layout_html` shape the rest. `art` and `reference` steer the generated backdrop. `note` takes anything else.

## Boundaries

- Art without text, or an illustration alone, is not a card: see [reimagine](reimagine.md) or [mascot](mascot.md).
- A finished raster that only needs resizing is `edit-card`; a card with a source spec is re-rendered by `create-card`.
- A slide title can be a card; a whole deck is not served.
- Moving pictures with the same copy: [promotion](../video-creator/promotion.md).

## Examples

No stored example; propose the leaf's representative sample unit: a single card for one destination (OG or x-post), in one named style.
