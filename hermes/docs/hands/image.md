# Image hands (image-creator)

Card and kit families. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Card family

Card now has four image-creator leaves: create/generate/edit/analyze-card.
Destinations are values of one subject (OG, social, headers, thumbnails, title
cards, X pair/carousel and custom WxH), not a menu or a new profile. The shared
card.py owns file-spec rendering/fit/measurement; create/card destination front
matter and CSS blocks are canonical. Generate styles own backdrop prompt prose
only. Exact text is font-rendered after generation; proposed allowance 3+1
across resumes requires explicit current-work user budget approval before paid
calls. Renders are local, isolated and exclusive; previews prove only local
appearance. Pair 7:8 is unverified, carousel scroll with 3 images user-observed,
X article 5:2 user-verified ratio only; all pixel defaults/gaps are authoring
choices. Do not post tests or inspect authenticated accounts without consent.
Retirement gate: keep creator-text-card and private-overlay 1:1 mapping until
handoff coverage, paid backdrop validation and old caller migration are proven.
New Card work routes to hands first; no changes to ports/toolsets/secrets.

Create-card's additive authored path accepts task-local static `layout_html`:
ImageCreator controls composition/typography while exact copy and local assets
remain bound inputs. Named templates remain available and saved template specs
are unchanged. Additional per-tile copy or repeated branding uses explicit
`copy_blocks`, not invented labels or hidden CSS text. Authored work uses a
resident conversation even for a named look/single tile, freezes its source/hash,
and checks real geometry, supported visibility and text overlap without shrinking.
Visual review still owns masks, occlusion, contrast, glyph coverage and use-size
readability. A template limitation is not permission to relax the Client's
design, buy new art, fall back silently or relabel an agent choice as human approval.

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
  from the selected categories; it stops before production. Round B
  needs approved sheet, item list and design lock. Defaults: 3 candidates,
  then 1 call/item + ceil(n/4) correctives; over 24 items requires explicit
  budget. Shared reference guidance does not guarantee exact state geometry.
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

`kit-images.py` is the shared local image helper (stdlib + ImageMagick):
fit, palette, atlas, measure. Atlas/measure have a 64-file limit and
reject nonempty output directories; split large kits into category
subsets and use fresh QA directories after corrections. Alpha bounds
come from alpha, not colour trimming: a hollow frame touches its canvas
corners and must not be cropped to its transparent interior. Palette
remapping detaches/reattaches alpha with scoped ImageMagick operations;
tests assert actual hues, not only a palette-size ceiling. Pixel native
intermediates live outside the final assets tree.

Verification (2026-09-06): all five leaves were exercised through the
image-creator CLI. A generated forest kit used one style sheet and three
item calls (4 total); approval stopped the first round correctly.
Independent normal/pressed drawings drifted in width and decoration,
and native inspection found magenta fringes missed by reduced sheets
and `key_px=0`. Failed assets remained marked in the manifest. Free
re-finishing from saved raws with `--cutout key --fuzz 30` removed the
fringes; exact state registration remains a `create-kit` use case, not
something a shared style anchor proves. Zero-call-cost finishing is
allowed even when the image-call grant forbids retries.

The deterministic pixel fixture produced eight assets, lossless atlas
crop round-trips, fixed state silhouettes and 9-slice corner checks.
Inspection correctly warned about pale borders on white. Tests also
cover title-band preservation, translucent alpha, palette hues and
hostile ZIP fixtures. Kenney sourcing delivered four selected arrows
with verified license/provenance. Two client-shaped Creator CLI runs
verified assistant brief -> generate-kit style question (zero spend),
and human request -> source-kit through the named image-creator A2A
peer -> delivery. A React component-library near miss stayed outside kit.
These are smoke fixtures, not a claim that every style has earned
production use. A further round (2026-09-06) went beyond that CLI smoke:
a full Creator session invoked the image-creator resident and resumed it
across two client-shaped brief turns, stopping Round A for the same
style-sheet approval gate before Round B batch production in the same
specialist session and Creator's own QA in the parent session. Independent
raw-pixel inspection
of that batch's potion/herb and inventory-panel assets (outside the style
sheet, which stays full-colour and is not native-pixel proof) found all
12 opaque colours inside the supplied palette (below the 16-colour cap),
binary 0/255 alpha, every
aligned 2x2 RGBA block matching its native source, and `kit.zip`'s CRC
and byte coverage exact across its 24 packaged members. Four image calls
were used (one sheet, three items); the resident session was closed after
accepting the test evidence. The taller potion was an approved fixture
variance; a small herb tie and minor panel-edge shading remain caveats.
Continued soak against real Telegram/client jobs remains future work; no legacy
technic is retired for kit because no existing family maps to it 1:1.
