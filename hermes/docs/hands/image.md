# Image hands (image-creator)

Icon, emoji, mascot, reimagine, card and kit families, plus the image-generation capability surface. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

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

- **Icon**: `source-icon`, `create-icon`, `generate-icon` (styles flat-minimal /
  glass / pixel / line / clay), `edit-icon`, `analyze-icon`. `source-icon` with
  `icon: twemoji:<name>` also covers published emoji glyphs, so there is no
  `source-emoji`.
- **Emoji**: `emoji-fit.sh` is the ONE home of the platform table (slack /
  discord 128 PNG, telegram 512 WebP + stroke, telegram-emoji 100 WebP, line
  180 PNG; `--spec` prints a row for `analyze-emoji`). `generate-emoji` runs in
  two rounds: without `anchor` it draws three character sheets and stops;
  `intent: revise` + `anchor:` draws the pack on that one reference. Props are
  drawn large, saturated and off the hair — small props vanish at 32 px.
  `create-emoji` renders text emoji (Hiragino Sans W8) from an items FILE.
  `analyze-emoji` reads packs over six tiles in halves; an unreached check is a
  GAP, never a pass.
- **Mascot**: `generate-mascot` runs in two rounds — three full-body concepts +
  a silhouette sheet (round A is exactly three looks: sheet, silhouette, the
  recommended one at native size), then `anchor:` + `pack:` (turnaround / poses
  / custom). A mascot's approved anchor is the `reference:` of its emoji pack.
  `edit-mascot` does background swap (including a chroma key that re-composites
  the cut-out on flat `#00ff00`), head / bust crop, resize and outline — never a
  recolour. `analyze-mascot` checks square, cut-out, silhouette, 64 px,
  light/dark, measured palette vs asked and identity vs anchor; line-art ink and
  highlights are tagged, not scored. No `source-` or `create-mascot`: a mascot
  is designed, not fetched, and a first-party mark becomes an icon set.
  `mascot-fit.sh` (corner flood or global key; `key_px` in its RESULT) draws on
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
`styles/*.md` CSS blocks. Generate's style references are backdrop prompt prose
only, never duplicated CSS. Exact text is font-rendered after generation.
Generate proposes 3+1 attempts across resumes but needs explicit current-work
user budget approval before paid calls.

Local HTML rendering uses an isolated offline agent-browser with frozen
assets/fonts, no inherited login/CDP, and exclusive output bundles. Full
panoramas render before exact PNG crops; text belongs to individual tiles, not
global destination crops. Previews prove only local appearance; gap previews are
configurable local simulations, never platform screenshots. X pair 7:8 is
UNVERIFIED, carousel scroll with 3 images is user-observed, and X article 5:2 is
a user-verified ratio, not the official 1500x600; all other pixel
defaults/gaps are authoring choices. Do not post tests or inspect authenticated
accounts without consent.

Create-card's additive authored path accepts task-local static `layout_html`
with exact copy/asset bindings and optional per-tile `copy_blocks`;
ImageCreator authors it, not the Client. It is the continuity path for centered
covers and custom typography — not an expansion of the template CSS allowlist
and not a silent legacy fallback. Named templates remain available and saved
template specs keep their template behavior; do not weaken a design to fit them.
Additional per-tile copy or repeated branding uses explicit `copy_blocks`, never
invented labels or hidden CSS text. Authored work uses a resident conversation
even for a named look or single tile, freezes its source with a hash, and
measures real geometry, supported visibility and text overlap without
auto-shrinking. Visual QA still owns masks, occlusion, contrast, glyph coverage
and use-size readability. A template limitation is not permission to relax the
Client's design, buy new art, fall back silently or relabel an agent choice as
human approval.

Card routes to the hands before `creator-text-card` (retirement gate:
[`overview.md`](./overview.md) "Migration"). Card needs no new profile, ports,
toolsets, secrets, test posts, authenticated access or gateway restart.

## Kit family

`image-creator-pipeline/<verb>/kit/` carries all five verbs. The family
is game props and UI images, not website components or 3D mesh files.
The user-facing starting fields are `what_for`, `style`, `contents` and
optional `reference`. `contents` is a comma-list; explicit `items` is the
whole list, replacing defaults. State variants are named items and count
toward the generation budget. Unknown styles/categories remain possible
through described inputs, with item sizes settled before production.

- `generate-kit`: pixel, 3d-render, cel-shaded, hand-painted, flat-vector
  and described looks. Round A proposes style sheets containing examples
  from the selected categories and stops before production (the style-sheet /
  list approval gate). Round B needs the approved sheet, item list and design
  lock. Defaults: 3 candidates, then 1 call/item + ceil(n/4) correctives; over
  24 items requires explicit budget. A shared style anchor does not guarantee
  exact state geometry — exact state registration is a `create-kit` use case.
- `create-kit`: deterministic flat-vector/pixel buttons, panels and bars,
  with state colours, SVG/PNG pairs and tested 9-slice borders. Its UI
  geometry is deliberately simple, not a generative style renderer.
  Flat-vector requires installed librsvg; no lower-fidelity fallback.
  Window slice insets protect the title band as well as the corners.
- `edit-kit`: lossless native-frame atlas or explicit fitting/palette
  changes; transforms may invalidate existing pivots/slicing metadata.
- `analyze-kit`: measured dimensions/alpha/palette plus visual findings;
  absent expectations remain GAP. It never performs a repair.
- `source-kit`: Kenney page discovery and CC0-verified ZIP retrieval,
  selected files under assets, source license and SHA-256 provenance.
  ZIP paths/symlinks/case collisions and decompressed size are checked
  before publication. READMEs are preserved, never quoted as licenses.

`kit-images.py` is the shared local image helper (stdlib + ImageMagick) and
owns fit, palette, atlas and measure. Atlas/measure have a 64-file limit and
reject stale nonempty QA/atlas output directories; split large kits into
category subsets and use fresh QA directories after corrections. Alpha bounds
come from alpha, not colour trimming: a hollow frame touches its canvas corners
and must not be cropped to its transparent interior. Palette remapping
detaches/reattaches alpha with scoped ImageMagick operations; tests assert
actual hues, not only a palette-size ceiling. Pixel native intermediates live
outside the final assets tree. Failed assets stay marked in the manifest.
Re-finishing from saved raws (e.g. `--cutout key`) costs no image call and is
allowed even when the image-call grant forbids retries. A reduced style sheet
or `key_px=0` is not native-pixel proof; inspect finished assets at native size.
Kit fixtures are smoke evidence, not proof that every style has earned
production use; soak against real client jobs is still pending.
