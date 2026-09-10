---
name: create-card
description: >-
  Exact-copy OG, social, header, thumbnail, hero or title CARD from approved
  text and local assets, deterministically font-rendered with HTML/CSS.
  Includes X pair candidates and 3/4-tile panoramas. Six named looks or a
  concretely authored described look. Not generated art, emoji, infographics,
  slide decks or kanban cards; finished raster adaptation is edit-card.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [card, og, social, panorama, typography, deterministic, free]
    category: hands
    hands: image-creator
    cost: free
    output: "card.html + spec.json + master.png + ordered tile-NN.png + tile-NN-preview.png + preview.png + manifest.json + layout.json; tiled: simulated-gap.png; carousel: simulated-display.png + simulated-display.json"
    form:
      title:
        required: true
        type: text
        label: "exact main copy; first tile only for panoramas"
      destination:
        required: true
        options: [og, x-post, x-article, x-header, x-pair, x-carousel, instagram, instagram-square, story, youtube-thumb, hero, slide-title, note]
        other: true
        label: "one destination, or explicit custom WxH (each axis 64..4096, bounded total canvas)"
      style:
        required: true
        options: [glass, flat-minimal, dark-pro, gradient-glow, paper, soft-3d]
        other: true
        label: "named look or verbatim described style; described requires task-local authored CSS, not a nearest-style fallback"
      subtitle:
        required: false
        label: "exact supporting text on tile 1"
      brand:
        required: false
        label: "exact brand text on tile 1 (logo pixels belong in motif)"
      label:
        required: false
        label: "short exact eyebrow on tile 1"
      meta:
        required: false
        label: "exact footer details on tile 1"
      background:
        required: false
        type: image
        label: "absolute local text-free PNG/JPEG/WebP; cover-fitted over the full panorama; no implicit fetch"
      motif:
        required: false
        type: image
        label: "absolute local PNG/JPEG/WebP, contained below copy on tile 1; rasterize a trusted SVG explicitly first"
      palette:
        required: false
        label: "three comma-separated #rrggbb values: surface,ink,accent; overrides style roles, not every gradient stop"
      font:
        required: false
        type: file
        label: "absolute local font; default installed Hiragino W6, error if absent; glyph coverage needs visual QA"
      tiles:
        required: false
        type: int
        label: "x-pair exactly 2; x-carousel 3 (default) or 4; conflicts rejected"
      tile:
        required: false
        label: "x-carousel portrait 4:5 (default), square 1:1 or tall 1:2; x-pair candidate only, 7:8 UNVERIFIED"
      tile_titles:
        required: false
        type: text
        label: "independent subheadings, one per line 'n: text'; tile 1 is below main title; tiles 2..4 each get their own heading"
        example: "1: Overview\n2: How it works\n3: Next step"
      gap:
        required: false
        type: int
        label: "legacy simulated-gap.png gap in source-image px, 0..128, default 16; separate carousel display preview uses canonical CSS-px width/gap, not this field"
      slug:
        required: false
        label: "lowercase words joined by hyphens; bundle identity recorded in spec, filenames stay stable"
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
3. Read the chosen canonical CSS block:
   [glass](references/styles/glass.md), [flat-minimal](references/styles/flat-minimal.md),
   [dark-pro](references/styles/dark-pro.md), [gradient-glow](references/styles/gradient-glow.md),
   [paper](references/styles/paper.md), [soft-3d](references/styles/soft-3d.md).
   For a described style read [the bounded spec contract](references/spec.md)
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
   their own tile insets. Never globally crop a text-bearing master into a
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
