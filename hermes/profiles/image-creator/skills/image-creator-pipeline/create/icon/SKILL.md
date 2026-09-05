---
name: create-icon
description: >-
  A favicon / Apple / PWA / maskable icon set derived deterministically from
  an existing first-party SVG mark: favicon.ico (16/32/48), square PNGs at
  the asked sizes, a flattened apple-icon, a maskable 512 with the mark
  inside the 80% safe zone, and the SVG itself. Nothing is redrawn or
  generated. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [icon, favicon, pwa, apple-icon, maskable, svg, free]
    category: hands
    hands: image-creator
    cost: free
    output: "favicon.ico + icon-<size>.png (16,32,48,180,192,512 by default) + apple-icon.png (180, flattened) + icon-maskable-512.png + icon.svg"
    form:
      source:
        required: true
        type: file
        label: "the first-party SVG mark (a raster master is edit-icon's job; a third-party logo is not yours to derive)"
        example: "~/Workspaces/Projects/Acme/public/logo.svg"
      background:
        required: false
        label: "flat fill behind apple-icon and maskable, #rrggbb (default #FFFFFF); `none` keeps the maskable transparent"
        example: "#0f172a"
      color:
        required: false
        label: "colour substituted for the SVG's currentColor, #rrggbb (without it currentColor renders black)"
        example: "#e26e54"
      sizes:
        required: false
        label: "square PNG sizes as a comma list (default 16,32,48,180,192,512)"
        example: "16,32,48,64,128,180,192,256,512"
      note:
        required: false
        type: text
---

<Procedure>

1. Read `source` as text: it must be an SVG (`<svg` present). If it uses
   `currentColor` and no `color` was given, stop with `Q1:` — the mark would
   render black. A PNG/JPG source is `no skill fits: raster master → edit-icon`.
2. Run:

   ```
   ${HERMES_SKILL_DIR}/scripts/logo-to-icons.sh <source.svg> <deliver> \
     [--bg "#rrggbb"|none] [--color "#rrggbb"] [--sizes 16,32,...]
   ```

   It writes the set and prints one `RESULT:` line: every file with its
   measured size, plus the mark's extent inside the maskable 512 (must be
   ≤ 410 px, the 80 % safe zone). Never call `image_generate` here — a set
   must be pixel-identical across sizes, and a model cannot do that.
3. Make one contact sheet for vision (`magick montage` of icon-16 scaled ×4,
   icon-32 ×2, icon-48, icon-180, icon-512 on a mid-grey background) and
   look at it once; then look at `icon-16.png` alone at native size.
4. `intent: revise` — rerun with the changed option; the same SVG + options
   reproduce the same bytes.

</Procedure>

<QA>

Every check with its evidence:

- **Files** — every name the `RESULT:` line lists exists at `deliver` and
  its measured size equals its name (`icon-192.png=192x192`, …).
- **Apple flattened** — `magick identify -format '%[channels] %[opaque]'
  apple-icon.png` prints `srgb 3.0 True` (two spaces after srgb are ImageMagick's) (no alpha channel, nothing
  transparent).
- **Safe zone** — `mark_extent_in_maskable` ≤ 410.
- **16 px legibility** — vision on `icon-16.png` at native size: the mark
  is still recognisable as the mark, not a smudge. If not, it is a finding
  for Creator (simplify the SVG), never a local redraw.
- **Identity across sizes** — vision on the contact sheet: the same mark,
  same colour, same proportions at every size.

</QA>

<Report>

`create-icon` + bg/colour used; the delivered directory and every file
with its measured size (the `RESULT:` line); each QA check with its
evidence; `spend: free`; anything Creator must decide (a mark that fails
at 16 px).

</Report>
