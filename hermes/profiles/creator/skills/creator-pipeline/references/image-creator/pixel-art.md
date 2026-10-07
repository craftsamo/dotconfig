# image-creator: pixel-art

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-pixel-art` — a grid-exact pixel still, either a source image reduced to a native grid or a described subject drawn cell by cell; fixed palette, no anti-aliasing; delivered as a native-resolution PNG master plus an integer nearest-neighbour preview and `palette.json`; nothing generated.

## Range

- Modes: reduce (needs a source image) or draw (from a described subject); any grid `WxH`; a named palette (pico8, gameboy, nes), a colour cap, or a palette locked from an earlier delivery so a batch stays consistent; transparent or solid background.
- The grid and palette are measured, so it suits sprites, avatars, icons, logo reductions and small scenes.
- It does not suit a photographic look or a painterly "pixel-style" image; a model-drawn pixel look is the `pixel` style of the generate leaves ([icon](icon.md), [emoji](emoji.md), [mascot](mascot.md), [kit](kit.md)) and guarantees no grid. A thin logo or diagonal needs a grid that can carry it.

## Where directions go

- `mode`, `grid` and `palette` fix the result; `source` or `subject` carries the content; `background` and `preview_scale` fine-tune; `note` takes the rest.

## Boundaries

- A base image to reduce comes from a generate leaf first, or from the user.
- Animation is not covered: this is a still.

## Examples

No stored example; propose the leaf's representative sample unit: one small still.
