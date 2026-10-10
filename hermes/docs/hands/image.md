# Image hands (image-creator)

Icon, emoji, mascot, reimagine, card, kit, diagram, pixel-art and illustration families, plus the image-generation capability surface. Read it when changing or commissioning an image leaf. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`image-creator` receives filled forms on A2A `:9907` (receive-only). Shared
contract: [`overview.md`](./overview.md).

## Image generation capabilities

`image_generate` advertises only what the configured provider's
`capabilities()` declares, failing closed to text-only. The `image-fallback`
chain provider must therefore declare capabilities: it reports the first
available member's surface, and for a call that carries images it skips
text-only members instead of falling through to a redraw — without that
declaration every chain profile loses `image_url` / `reference_image_urls`
from the tool schema. After an upstream change, verify with
`_build_dynamic_image_schema()` under the profile's `HERMES_HOME`
(`plugins/image_gen/image-fallback/tests`).

## Icon, emoji and mascot families

- **Icon**: `source-icon`, `create-icon`, `generate-icon`, `edit-icon`,
  `analyze-icon`. `source-icon` with `icon: twemoji:<name>` also covers
  published emoji glyphs, so there is no `source-emoji`.

  **Official brand marks:** `source-icon` with `official: yes` delivers a
  vendor's own logo file byte for byte from its brand page or press kit —
  never redrawn, recoloured or generated; aggregators (Simple Icons, svgl) are
  named as such — with `provenance.json` and a `terms.txt` usage summary. A
  vendor without a distributed mark is reported, not approximated.
  `brand-check.py` (no network) checks each SVG renders non-blank, and records
  sha256s and a byte-compare of the delivery against the archive member;
  `provenance.json` is never overwritten. Vendor findings and the recipe for
  bot-protected brand pages live in the leaf's `references/`.

- **Emoji**: `emoji-fit.sh` is the ONE home of the platform table (sizes and
  formats; `--spec` prints a row for `analyze-emoji`). `generate-emoji` runs in
  two rounds: without `anchor` it draws three character sheets and stops;
  `intent: revise` + `anchor:` draws the pack on that one reference. Props are
  drawn large, saturated and off the hair — small props vanish at 32 px.
  `create-emoji` renders text emoji from an items FILE. `analyze-emoji` reads
  packs over six tiles in halves; an unreached check is a GAP, never a pass.
- **Mascot**: `generate-mascot` runs in two rounds — three full-body concepts +
  a silhouette sheet (round A is exactly three looks), then `anchor:` + `pack:`
  (turnaround / poses / custom). A mascot's approved anchor is the `reference:`
  of its emoji pack. `edit-mascot` does background swap, head / bust crop,
  resize and outline — never a recolour. `analyze-mascot` checks square,
  cut-out, silhouette, 64 px, light/dark, measured palette vs asked and identity
  vs anchor. No `source-` or `create-mascot`: a mascot is designed, not
  fetched, and a first-party mark becomes an icon set. `mascot-fit.sh` keys on
  chroma green (magenta when the palette has green), never white — on white,
  `key_px` counts eye whites and speculars.

## Reimagine family

One metered leaf, `generate-reimagine`: a client's photo re-rendered in a style
(3d-character, comic-book, chibi, 70s-street, 80s-anime, or described) with the
same subject, pose and composition. The photo is the edit input (`image_url`),
never a `reference_image_urls` entry. A human client consents to the upload in
the same `clarify` round as the style, never after. The hands look at the photo
once and write `subject.md`, the identity lock every look is judged against
(`keep: identity` relaxes it to the subject alone). One or several styles per
form, two candidates each, finished to the photo's own size next to a
photo-plus-candidates sheet per style; the budget is 2 + 1 corrective PER STYLE.
Every style reference opens with a **Medium** line (redraw / repaint / rebuild
/ re-photograph; the photo's own texture must go) and the prompt leads with it —
otherwise an edit model returns the photo with a filter. Prompts end with the
canvas spelled out; every raw is measured as it lands, and a transposed raw is
marked failed, never cover-cropped. A corrective rebuilds the sheet with every
candidate. No edit- or analyze-reimagine: size and format are the leaf's own
fields and identity against the photo is its own QA.

## Card family

Card is one image subject with four leaves: create/generate/edit/analyze-card.
Destinations are values of one subject (OG, social, headers, thumbnails, title
cards, X pair/carousel and custom WxH), not a menu or a new profile. The shared
`scripts/card.py` owns file-spec rendering/fit/measurement and consumes the
canonical `create/card/references/destination/` scalar front matter and
`styles/*.md` CSS blocks (bounded text effects on copy; compositing and
gradient masks only on layers that paint below it) plus an optional seeded
texture that card.py renders offline with ImageMagick, since CSS alone cannot
draw grain. Generate's style references are backdrop prompt prose only, never
duplicated CSS. Exact text is font-rendered after generation. Generate needs
explicit current-work user budget approval before paid calls.

Local HTML rendering uses an isolated offline agent-browser with frozen
assets/fonts, no inherited login/CDP, and exclusive output bundles. Full
panoramas render before exact PNG crops; text belongs to individual tiles, not
global destination crops. Previews prove only local appearance; gap previews are
configurable local simulations, never platform screenshots. X pair 7:8 is
UNVERIFIED, carousel scroll with 3 images is user-observed, and X article 5:2 is
a user-verified ratio, not the official 1500x600; all other pixel
defaults/gaps are authoring choices. Do not post tests or inspect authenticated
accounts without consent.

Create-card's authored path accepts task-local static `layout_html` with exact
copy/asset bindings and optional per-tile `copy_blocks`; ImageCreator authors
it, not the Client. It is the continuity path for centered covers and custom
typography — not an expansion of the template CSS allowlist and not a silent
fallback. Saved template specs keep their template behavior; do not weaken a
design to fit them. Additional per-tile copy or repeated branding uses explicit
`copy_blocks`, never invented labels or hidden CSS text. Authored work uses a
resident conversation even for a named look or single tile, freezes its source
with a hash, and measures real geometry, supported visibility and text overlap
without auto-shrinking. Visual QA still owns masks, occlusion, contrast, glyph
coverage and use-size readability. A template limitation is not permission to
relax the Client's design, buy new art, fall back silently or relabel an agent
choice as human approval.

## Kit family

`image-creator-pipeline/<verb>/kit/` carries all five verbs. The family
is game props and UI images, not website components or 3D mesh files.
The user-facing starting fields are `what_for`, `style`, `contents` and
optional `reference`. `contents` is a comma-list; explicit `items` is the
whole list, replacing defaults. State variants are named items and count
toward the generation budget. Unknown styles/categories remain possible
through described inputs, with item sizes settled before production.

- `generate-kit`: Round A proposes style sheets containing examples from the
  selected categories and stops before production (the style-sheet / list
  approval gate). Round B needs the approved sheet, item list and design lock;
  large item counts require an explicit budget. A shared style anchor does not
  guarantee exact state geometry — exact state registration is a `create-kit`
  use case.
- `create-kit`: deterministic flat-vector/pixel buttons, panels and bars, with
  state colours, SVG/PNG pairs and tested 9-slice borders; deliberately simple
  UI geometry. Flat-vector requires installed librsvg, no lower-fidelity
  fallback. Window slice insets protect the title band as well as the corners.
- `edit-kit`: lossless native-frame atlas or explicit fitting/palette changes;
  transforms may invalidate existing pivots/slicing metadata.
- `analyze-kit`: measured dimensions/alpha/palette plus visual findings;
  absent expectations remain GAP. It never performs a repair.
- `source-kit`: Kenney page discovery and CC0-verified ZIP retrieval with
  source license and SHA-256 provenance; ZIP paths/symlinks and decompressed
  size are checked before publication. READMEs are preserved, never quoted as
  licenses.

`kit-images.py` is the shared local image helper (stdlib + ImageMagick) for
fit, palette, atlas and measure; it rejects stale nonempty QA/atlas output
directories, so use fresh ones after corrections. Alpha bounds come from alpha,
not colour trimming: a hollow frame touches its canvas corners and must not be
cropped to its transparent interior. Pixel native intermediates live outside
the final assets tree. Failed assets stay marked in the manifest. Re-finishing
from saved raws (e.g. `--cutout key`) costs no image call and is allowed even
when the image-call grant forbids retries. A reduced style sheet or `key_px=0`
is not native-pixel proof; inspect finished assets at native size. Kit fixtures
are smoke evidence, not proof that every style has earned production use.

## Diagram family

`image-creator-pipeline/create/diagram/` carries one verb. `create-diagram`
draws an architecture, flow, sequence or concept diagram deterministically as
one self-contained HTML file with inline SVG plus 1x and 2x PNG renders, from
the nodes, edges and exact labels in the form; nothing is generated and it is
free.

- **Engines:** upstream `architecture-diagram` (architecture) and the optional
  `concept-diagrams` (flow, sequence, concept), attached through the hands'
  `skills.external_dirs`; the leaf takes their drawing conventions only, never
  their clarify or intake.
- **`diagram.py render`:** rejects remote URLs, `<script>` and stylesheet links,
  requires every label of `labels.json` in the SVG text, and renders offline at
  1x and 2x, requiring identical screenshots per scale and no browser errors,
  into a new directory.

## Pixel-art family

`image-creator-pipeline/create/pixel-art/` carries one verb.
`create-pixel-art` delivers a grid-exact pixel still (sprite, avatar, icon,
logo reduction, small scene) as a native-resolution PNG master plus an integer
nearest-neighbour preview, either by reducing a source image to the grid
(`mode: reduce`) or by drawing a described subject cell by cell
(`mode: draw`); the palette is fixed, there is no anti-aliasing, nothing is
generated by a model and it is free. A model-drawn "pixel" look is not this
leaf but the `pixel` style of the generate leaves, which guarantees neither
grid nor palette.

- **`render-pixel-art.sh`:** `reduce` mode: explicit fit, gravity and alpha
  policy through `magick`, quantized through the upstream `pixel_art.py`
  backend, previewed by integer nearest-neighbour upscale.
- **`palette-extract.py`:** locks one palette across a batch so items are never
  quantized independently.
- **`pixel.py`:** `draw` renders a cell map (rows of palette keys, `.`
  transparent) into `native.png`, `preview.png` and `palette.json` in a new
  directory, refusing ragged rows and unknown keys; `check` verifies native
  size, palette membership, no partial alpha, integer preview scale and
  uniform blocks, and writes nothing.

## Illustration family

`image-creator-pipeline/generate/illustration/` carries one verb.
`generate-illustration` delivers a model-generated, text-free still (cover,
hero, editorial or article illustration, thumbnail art, background, document or
social art) in a named or described look, as variants at an exact size and
format next to a contact sheet with one recommended variant. Exact text never
goes into the pixels: that is a card (`create-card`, `generate-card`); icons,
emoji, mascots, kits and photo reimaginings have their own leaves. It is
metered through core `image_generate`: failed calls count and `attempts.json`
is the tally. A reference image leaves the machine only with explicit upload
consent. Variants are normalized with the shared `img-postprocess.sh`; prompt
craft lives in the leaf's `references/craft-notes.md`.
