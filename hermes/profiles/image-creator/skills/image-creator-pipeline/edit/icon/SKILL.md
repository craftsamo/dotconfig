---
name: edit-icon
description: >-
  Deterministic edits on an existing icon file (PNG / WebP / JPG / SVG):
  recolour a monochrome mark, swap or remove its background (transparent,
  rounded tile, flat fill), cut a subject out of a flat background, and
  emit the result at one or more square sizes. Nothing is redrawn or
  generated. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [icon, edit, recolor, background, resize, cutout, free]
    category: hands
    hands: image-creator
    cost: free
    output: "icon_<slug>_<size>.png per size (+ icon_<slug>.svg when the source is an SVG)"
    form:
      source:
        required: true
        type: file
        label: "the icon to edit (PNG / WebP / JPG / SVG)"
        example: "~/Workspaces/Projects/Acme/.agent/deliverables/icons/icon_rocket_512.png"
      color:
        required: false
        label: "recolour: every opaque pixel of a raster takes this #rrggbb (monochrome marks only); an SVG only gets its currentColor substituted"
        example: "#16a34a"
      background:
        required: false
        options: [transparent, tile]
        other: true
        label: "transparent (default) | tile (on a rounded tile of tile_color) | #rrggbb flat fill"
      tile_color:
        required: false
        label: "tile colour for background: tile, #rrggbb (default #22d3ee)"
      cutout:
        required: false
        options: ["yes", "no"]
        label: "remove the source's flat background first (default no; needed before a background swap on an opaque raster)"
      sizes:
        required: false
        label: "square output edges as a comma list (default: the source's shorter edge; 512 for an SVG)"
        example: "512,256,64"
      pad:
        required: false
        label: "fraction of the edge kept clear around the mark (default 0 — the source's own framing)"
      slug:
        required: false
        label: "filename stem (default: the source's stem without icon_ / _<size>)"
      note:
        required: false
        type: text
---

<Procedure>

1. At least one of `color`, `background`, `cutout: yes`, `sizes`, `pad` must
   be present, or there is nothing to edit — `Q1:` asking which. Measure the
   source first: `magick identify -format '%w %h %[channels] %[opaque]'`.
   An opaque raster (`True`) with a `background` other than a flat fill and
   no `cutout: yes` would paint the whole square — say so as `Q1:` and
   recommend `cutout: yes`. A `color` on a multi-colour raster flattens it
   to one colour — if the source is visibly multi-colour (vision), `Q1:`.
2. Run:

   ```
   ${HERMES_SKILL_DIR}/scripts/icon-edit.sh <source> <deliver> \
     [--color "#rrggbb"] [--background transparent|tile|"#rrggbb"] [--tile "#rrggbb"] \
     [--cutout] [--sizes 512,256,64] [--pad F] [--slug <slug>]
   ```

   One `RESULT:` line per output (measured size, bytes, channels, coverage,
   corner_alpha). A cut-out that ate part of the mark or left a fringe is
   re-run with `--fuzz 5%` / `--fuzz 16%` — free.
3. Look with vision: the largest output at native size on a contrasting
   background, then the smallest one at native size.
4. `intent: revise` — rerun with the changed option; same input + options
   reproduce the same bytes.

</Procedure>

<QA>

Every check with its evidence, per output:

- **Dimensions** — `width=<size> height=<size>` in `RESULT:` for every size
  asked.
- **Background** — `transparent`: `corner_alpha=0` and `coverage` < 0.9;
  `tile`: `coverage` ≈ 0.95; `#rrggbb`: `coverage=1`.
- **Colour** — with `color`: vision, the mark is that colour and nothing
  else changed (shape, framing); for an SVG, `grep` the colour in the
  written `icon_<slug>.svg`.
- **Cut-out** — with `cutout: yes`: vision, no ghost of the old background,
  no holes, no fringe.
- **Smallest size** — the mark still reads at the smallest output.

</QA>

<Report>

`edit-icon` + the edits applied; every output path with its `RESULT:`
numbers and QA verdicts; `spend: free`; anything Creator must decide.

</Report>
