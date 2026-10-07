# image-creator: kit

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-kit` — a game props and UI asset kit in one visual language (world props, icon sets, buttons, panels, bars), drawn by an image model; transparent PNG per item.
- `create-kit` — a deterministic game-UI kit (buttons, panels, bars) as flat-vector or pixel art: SVG and PNG per item and state, with 9-slice borders for stretchable pieces.
- `source-kit` — one free Kenney CC0 asset pack (icon, UI, tile sets) extracted as supplied, with provenance and license; nothing drawn.
- `edit-kit` — finishes or packages an existing kit: cutout, contain-fit, pixel-grid resampling, shared-palette remap, PNG atlas; no new drawing.
- `analyze-kit` — findings on an existing kit: inventory, dimensions, alpha, palette and style coherence, readability at use size, button-state alignment, bar registration.

## Range

- `generate-kit` is two rounds: three style-sheet candidates with an item list first, then the individual assets on the chosen sheet. UI states (normal, pressed, hover, disabled) each count as an item.
- Generated styles: pixel, 3d-render, cel-shaded, hand-painted, flat-vector, isometric, low-poly, neon, stained-glass, or a described one. Perspective: side, top-down, isometric, front. Contents: world-props, icon-set, buttons, panels, bars, or a described category with agreed items.
- `create-kit` offers only flat-vector and pixel, with generic geometry and exact, interchangeable states.
- Not served: web component libraries, 3D models, engine-ready UI code.

## Where directions go

- `style` carries the look; one file per option under `references/styles/` of `generate-kit` (and of `create-kit` for its two), e.g. `skill_view(name="generate-kit", file_path="references/styles/pixel.md")`. Category vocabulary lives under `references/contents/` of `generate-kit`.
- `what_for`, `contents`, `items`, `perspective`, `palette`, `reference`, `note` carry the rest. Explicit `items` replace defaults.

## Boundaries

- Exact controls and 9-slice borders: `create-kit`; stock art with its own look: `source-kit`. A single glyph: [icon](icon.md).
- A hero character for the game: [mascot](mascot.md).

## Examples

No stored example; propose the leaf's representative sample unit: the style-sheet round, one sheet holding representative props and UI plus the item list, in one style.
