---
name: create-card
description: >-
  Exact-copy OG, social, header, thumbnail, hero or title CARD from approved
  text and local assets, deterministically font-rendered with HTML/CSS.
  Includes X pair candidates and 3/4-tile panoramas. Named templates or
  task-authored layouts and typography. Not generated art, emoji, infographics,
  slide decks or kanban cards; finished raster adaptation is edit-card.
version: 1.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [card, og, social, panorama, typography, deterministic, free]
    category: hands
    hands: image-creator
    cost: free
    output: "HTML/spec + PNG master/tiles/previews + manifest/layout/QA; authored: frozen source; tiled: gap/display simulations"
    form:
      title:
        required: true
        type: text
        label: "exact main copy on tile 1"
      destination:
        required: true
        options: [og, x-post, x-article, x-header, x-pair, x-carousel, instagram, instagram-square, story, youtube-thumb, hero, slide-title, note]
        other: true
        label: "destination or custom WxH; local bounds in spec"
      style:
        required: true
        options: [glass, flat-minimal, dark-pro, gradient-glow, paper, soft-3d]
        other: true
        label: "named look or verbatim visual direction; no nearest-style fallback"
      layout_html:
        required: false
        type: file
        label: "ImageCreator-authored static layout; client need not supply code"
      copy_blocks:
        required: false
        label: "additional exact {id,tile,text} blocks for authored layouts"
      subtitle:
        required: false
        label: "exact supporting text on tile 1"
      brand:
        required: false
        label: "exact brand text on tile 1"
      label:
        required: false
        label: "exact eyebrow on tile 1"
      meta:
        required: false
        label: "exact metadata on tile 1"
      background:
        required: false
        type: image
        label: "local text-free PNG/JPEG/WebP; no implicit fetch"
      motif:
        required: false
        type: image
        label: "local PNG/JPEG/WebP; trusted SVG rasterization first"
      palette:
        required: false
        label: "template surface,ink,accent as three #rrggbb values"
      font:
        required: false
        type: file
        label: "local font; default installed Hiragino W6"
      tiles:
        required: false
        type: int
        label: "x-pair 2; x-carousel 3 (default) or 4"
      tile:
        required: false
        label: "carousel portrait/square/tall; pair candidate 7:8 UNVERIFIED"
      tile_titles:
        required: false
        type: text
        label: "per-tile heading 'n: text'; tile 1 is a subheading"
        example: "1: Overview\n2: How it works\n3: Next step"
      gap:
        required: false
        type: int
        label: "source-pixel simulation gap, 0..128, default 16; not CSS gap"
      slug:
        required: false
        label: "lowercase hyphenated bundle identity"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm exact copy, destination and style from the form. Text-only emoji
   uses create-emoji; a generated backdrop uses generate-card. No generated
   pixels, remote assets or paid calls here. A note imposing a new layout or
   protected element is a real requirement: implement within the contract or
   return a finding, never silently ignore it.
2. Read the chosen destination's canonical scalar front matter and its caveats:
   [og](references/destination/og.md), [x-post](references/destination/x-post.md),
   [x-article](references/destination/x-article.md), [x-header](references/destination/x-header.md),
   [x-pair](references/destination/x-pair.md), [x-carousel](references/destination/x-carousel.md),
   [instagram](references/destination/instagram.md), [instagram-square](references/destination/instagram-square.md),
   [story](references/destination/story.md), [youtube-thumb](references/destination/youtube-thumb.md),
   [hero](references/destination/hero.md), [slide-title](references/destination/slide-title.md),
   [note](references/destination/note.md). Custom destination is a literal `WxH`.
   These are authoring defaults, not verified upload caps or platform-safe zones.
3. Choose the implementation by the actual layout requirements, not the style
   name alone. For a centered cover, custom typography, additional copy regions
   or source revision that the template cannot express, author `layout_html`
   using [the authored contract](references/spec.md#authored-layouts).
   ImageCreator writes the source; do not ask the client to supply HTML/CSS.
   Do not weaken protected placement or copy to fit a template. Use `kind="work"`
   for authored work even when the requested look is named and the card is single.
   A named look still guides authored CSS and visual QA; it does not inject a
   template into the authored page. Existing editable source informs the revision;
   preserve the original, never execute an unreviewed source script.

   For template work, read the chosen canonical CSS block:
   [glass](references/styles/glass.md), [flat-minimal](references/styles/flat-minimal.md),
   [dark-pro](references/styles/dark-pro.md), [gradient-glow](references/styles/gradient-glow.md),
   [paper](references/styles/paper.md), [soft-3d](references/styles/soft-3d.md).
   For a template's described appearance read [the bounded spec contract](references/spec.md)
   and author concrete CSS in the task directory. Preserve the description in
   `style` and pass absolute `style_css` in the execution JSON. Never modify the
   managed references or pretend a named fallback fulfills the description.
4. Write `<task>/card-spec.json` from the filled form using the spec contract.
   Japanese copy travels in that file, never argv. Localize only already
   approved assets; supplied files do not authorize a network fetch. Output
   bundle must be NEW, even on revise. Run a standalone command:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/card.py create <absolute-spec.json> --out <new-absolute-bundle>
   ```

   Requires installed agent-browser and ImageMagick, never auto-installs. The
   helper owns an isolated namespace/session with sanitized environment, no
   inherited login/CDP/plugins, offline page and inline frozen assets/fonts.
   It awaits font/image decoding, checks text bounds, takes two stable PNG
   snapshots and closes its own session on success/error. Layout failure is a
   stopped run with diagnostics, not a successful clipped card. Use background
   execution/polling if an environment approaches the terminal time limit.
5. For pair/carousel the full panorama is rendered FIRST, then exact adjacent
   lossless crops. Main title/brand/meta stay on tile 1; tile_titles belong to
   their own tiles. Authored `copy_blocks` supply explicit additional text or
   repeated branding on other tiles; never invent repetition or new copy.
   Never globally crop a text-bearing master into a
   different destination: rerender its spec at the new canvas. View the gap
   simulation, not as an X screenshot or crop guarantee. For carousel use
   simulated-display.png with its JSON label: each image 360 CSS px wide,
   effective image gap 6 CSS px, 1 raster px per CSS px. Do not bake gaps into
   upload tiles or compensate with seam-content crops.
6. Run the bounded QA below, appending each look's finding to `<bundle>/qa.md`
   before the next look. Revise the exact failed input/layout once into a fresh
   bundle; if it still fails, report the finding. Never shrink unreadable copy
   without informing Creator, retry blindly or edit the managed helper.

</Procedure>

<QA>

- Measurements: manifest canvas matches destination; layout.json has only
  `ok: true` copy rows; two decoded RGBA snapshots agree; tile reassembly equals
  master decoded pixels. These checks prove geometry/stability, not visual quality.
- Authored layouts additionally retain source-layout.html and its manifest hash.
  Check binding/visibility/overlap findings. There is no automatic font shrinking;
  `display_font_px` measures reduced-size text, not a readability PASS. Complex
  masks, painted occlusion, contrast and glyph coverage still need visual review.
- One overview look at preview.png (carousel: simulated-display.png with its
  declared CSS-px width/gap; pair: simulated-gap.png) for hierarchy,
  intended style and seam continuity. One native-size look per tile for exact
  Japanese/Latin readback, missing glyphs, clipping, motif and contrast. One
  reduced-size look per tile (360px wide; youtube-thumb 168px) for readability.
  Use local scratch resizes, not additional model generations. At most 1+2N
  looks for N delivered tiles. Record uncertain visual checks as UNVERIFIED.
- Style cues must match the selected reference or concrete custom design.
  Content in note must be accounted for. Numeric font readiness is not glyph
  coverage or contrast certification.
- X pair 7:8 remains an unverified candidate. X carousel 3-image scrolling is
  user-observed, not a verified 4-image or no-crop rule. No test posting or
  authenticated platform inspection without separate user authorization.

</QA>

<Report>

create-card; absolute spec/HTML/master/tile/preview/manifest/QA paths; style and
resolved destination dimensions; ordered tile list; measured text bounds and
RGBA stability/reassembly evidence; visual readback and style/contrast verdicts
separately; `spend: free`; any unresolved requirement. Explicitly label the gap
preview LOCAL SIMULATION and x-pair UNVERIFIED CANDIDATE, not platform evidence.

</Report>
