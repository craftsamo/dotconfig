# Image hands (image-creator)

Icon, emoji, mascot, reimagine, card, kit, diagram, pixel-art and illustration families, plus the image-generation capability surface. Read it when changing or commissioning an image leaf. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`image-creator` receives filled forms on A2A `:9907` (receive-only). Shared
contract: [`overview.md`](./overview.md). The leaves' `SKILL.md` and scripts own
forms, sizes and procedures; this doc keeps family boundaries and guards.

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

- **Icon**: `source-icon` with `icon: twemoji:<name>` also covers published
  emoji glyphs, so there is no `source-emoji`. `source-icon` with
  `official: yes` delivers a vendor's own logo file byte for byte from its brand
  page or press kit — never redrawn, recoloured or generated; aggregators are
  named as such, and a vendor without a distributed mark is reported, not
  approximated. `provenance.json` is never overwritten.
- **Emoji**: `emoji-fit.sh` is the ONE home of the platform table.
  `generate-emoji` runs in two rounds: without `anchor` it draws three
  character sheets and stops; `intent: revise` + `anchor:` draws the pack on
  that one reference. `analyze-emoji`: an unreached check is a GAP, never a
  pass.
- **Mascot**: `generate-mascot` runs in two rounds (round A is exactly three
  looks), then `anchor:` + `pack:`. A mascot's approved anchor is the
  `reference:` of its emoji pack. `edit-mascot` never recolours. No `source-` or
  `create-mascot`: a mascot is designed, not fetched, and a first-party mark
  becomes an icon set. `mascot-fit.sh` keys on chroma green (magenta when the
  palette has green), never white — on white, `key_px` counts eye whites and
  speculars.

## Reimagine family

One metered leaf, `generate-reimagine`: a client's photo re-rendered in a style
with the same subject, pose and composition. The photo is the edit input
(`image_url`), never a `reference_image_urls` entry. A human client consents to
the upload in the same `clarify` round as the style, never after. The hands
look at the photo once and write `subject.md`, the identity lock every look is
judged against. The budget is 2 + 1 corrective PER STYLE. Every style
reference opens with a **Medium** line (redraw / repaint / rebuild /
re-photograph; the photo's own texture must go) and the prompt leads with it —
otherwise an edit model returns the photo with a filter. Every raw is measured
as it lands, and a transposed raw is marked failed, never cover-cropped. No
edit- or analyze-reimagine: size and format are the leaf's own fields and
identity against the photo is its own QA.

## Card family

Card is one image subject with four leaves: create/generate/edit/analyze-card.
Destinations are values of one subject (OG, social, headers, thumbnails, title
cards, X pair/carousel and custom WxH), not a menu or a new profile. The shared
`scripts/card.py` owns file-spec rendering/fit/measurement and consumes the
canonical `create/card/references/destination/` front matter and `styles/*.md`
CSS blocks. Generate's style references are backdrop prompt prose only, never
duplicated CSS. Exact text is font-rendered after generation, never drawn by the
model. Generate needs explicit current-work user budget approval before paid
calls.

Local HTML rendering uses an isolated offline agent-browser with frozen
assets/fonts, no inherited login/CDP, and exclusive output bundles. Previews
prove only local appearance; gap previews are local simulations, never platform
screenshots. X pair 7:8 is UNVERIFIED, carousel scroll with 3 images is
user-observed, and X article 5:2 is a user-verified ratio, not the official
1500x600; all other pixel defaults/gaps are authoring choices. Do not post tests
or inspect authenticated accounts without consent.

Create-card's authored path accepts task-local static `layout_html` with exact
copy/asset bindings and optional per-tile `copy_blocks`; ImageCreator authors
it, not the Client. It is the continuity path for centered covers and custom
typography — not an expansion of the template CSS allowlist and not a silent
fallback. Saved template specs keep their template behavior; do not weaken a
design to fit them. Per-tile copy or repeated branding uses explicit
`copy_blocks`, never invented labels or hidden CSS text. Authored work uses a
resident conversation, freezes its source with a hash, and measures real
geometry and text overlap without auto-shrinking; visual QA still owns masks,
occlusion, contrast and use-size readability. A template limitation is not
permission to relax the Client's design, buy new art, fall back silently or
relabel an agent choice as human approval.

## Kit family

`image-creator-pipeline/<verb>/kit/` carries all five verbs. The family is
game props and UI images, not website components or 3D mesh files. `contents`
is a comma-list; explicit `items` is the whole list, replacing defaults. State
variants are named items and count toward the generation budget.

- `generate-kit`: Round A proposes style sheets and stops before production
  (the style-sheet / list approval gate). Round B needs the approved sheet,
  item list and design lock; large item counts require an explicit budget. A
  shared style anchor does not guarantee exact state geometry — exact state
  registration is a `create-kit` use case.
- `create-kit`: deterministic flat-vector/pixel UI geometry with tested 9-slice
  borders. Flat-vector requires installed librsvg, no lower-fidelity fallback.
- `edit-kit`: lossless atlas or explicit fitting/palette changes; transforms may
  invalidate existing pivots/slicing metadata.
- `analyze-kit`: measurements plus visual findings; absent expectations remain
  GAP. It never performs a repair.
- `source-kit`: Kenney CC0-verified retrieval with source license and SHA-256
  provenance. READMEs are preserved, never quoted as licenses.

`kit-images.py` rejects stale nonempty QA/atlas output directories, so use fresh
ones after corrections. Alpha bounds come from alpha, not colour trimming: a
hollow frame touches its canvas corners and must not be cropped to its
transparent interior. Failed assets stay marked in the manifest. Re-finishing
from saved raws costs no image call and is allowed even when the image-call
grant forbids retries. A reduced style sheet or `key_px=0` is not native-pixel
proof; inspect finished assets at native size. Kit fixtures are smoke evidence,
not proof that every style has earned production use.

## Diagram family

`create-diagram` (one verb, free, nothing generated) draws an architecture,
flow, sequence or concept diagram deterministically as one self-contained HTML
file with inline SVG plus 1x and 2x PNG renders, from the nodes, edges and exact
labels in the form. It takes the drawing conventions of the upstream
`architecture-diagram` and optional `concept-diagrams` skills (attached through
the hands' `skills.external_dirs`) only, never their clarify or intake.
`diagram.py render` fails closed: remote URLs, scripts and a missing label are
rejected, and the render is offline.

## Pixel-art family

`create-pixel-art` (one verb, free, nothing generated by a model) delivers a
grid-exact pixel still as a native-resolution PNG master plus an integer
nearest-neighbour preview, by reducing a source image to the grid
(`mode: reduce`) or drawing a described subject cell by cell (`mode: draw`). The
palette is fixed and there is no anti-aliasing; a batch locks one palette so
items are never quantized independently. A model-drawn "pixel" look is not this
leaf but the `pixel` style of the generate leaves, which guarantees neither grid
nor palette.

## Illustration family

`generate-illustration` delivers a model-generated, text-free still (cover,
hero, editorial or article illustration, thumbnail art, background, document or
social art) as variants next to a contact sheet with one recommended variant.
Exact text never goes into the pixels: that is a card (`create-card`,
`generate-card`); icons, emoji, mascots, kits and photo reimaginings have their
own leaves. It is metered through core `image_generate`: failed calls count and
`attempts.json` is the tally. A reference image leaves the machine only with
explicit upload consent.
