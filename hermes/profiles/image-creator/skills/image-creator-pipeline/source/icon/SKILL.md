---
name: source-icon
description: >-
  One published icon fetched from the open icon libraries on the Iconify
  API (Lucide, Tabler, Phosphor, Material Symbols, Simple Icons brand
  marks, … 200k+ glyphs, no key), delivered as the source SVG plus a PNG
  in the asked colour, size and background, with its license recorded.
  Nothing is drawn or generated. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [icon, iconify, svg, png, source, free]
    category: hands
    hands: image-creator
    cost: free
    output: "icon_<slug>.svg + icon_<slug>_<size>.png (size x size, default 512) + a LICENSE line"
    form:
      icon:
        required: true
        label: "Iconify id `set:name`, or a search word when the id is unknown"
        example: "lucide:rocket / simple-icons:github / rocket"
      color:
        required: false
        label: "glyph colour, #rrggbb (default #000000; ignored on a tile)"
        example: "#e4572e"
      size:
        required: false
        type: int
        label: "canvas edge in px; the PNG is square (default 512)"
      background:
        required: false
        options: [transparent, tile]
        other: true
        label: "transparent (default) | tile (white glyph on a rounded tile) | #rrggbb flat fill"
      tile_color:
        required: false
        label: "tile colour for background: tile, #rrggbb (default #22d3ee)"
      pad:
        required: false
        label: "transparent/fill only: fraction of the edge kept clear around the glyph (default 0)"
        example: "0.1"
      slug:
        required: false
        label: "filename stem (default: the id with `:` → `-`)"
      note:
        required: false
        type: text
---

<Procedure>

1. If `icon` is a WORD rather than a `set:name` id, run
   `${HERMES_SKILL_DIR}/scripts/icon-fetch.sh --search <word>` and return
   the `CANDIDATES:` list as `Q1:` with your recommendation (glyph choice is
   Creator's, not yours). Stop there.
2. Otherwise run:

   ```
   ${HERMES_SKILL_DIR}/scripts/icon-fetch.sh --icon <set:name> --out <deliver> \
     [--color "#rrggbb"] [--size N] [--background transparent|tile|"#rrggbb"] \
     [--tile "#rrggbb"] [--pad F] [--slug <slug>]
   ```

   It prints one `RESULT:` line (png, svg, measured width / height / bytes,
   channels, glyph coverage, set) and one `LICENSE:` line. An id the API
   does not know exits non-zero with `icon not found` — offer `--search`
   candidates as `Q1:`, never substitute.
3. Inspect the PNG with vision on a contrasting background: the glyph is the
   icon asked for, whole, centred, in the asked colour (white on a tile),
   with clean edges.
4. `intent: revise` — rerun with the changed option; the same id + options
   reproduce the same bytes.

</Procedure>

<QA>

Every check with its evidence, never "looks fine":

- **Identity** — `icon=` in `RESULT:` equals the `icon` input.
- **Dimensions** — `width=<size> height=<size>` (default 512).
- **Background** — `transparent`: `channels` includes alpha and `coverage`
  is between 0.02 and 0.9 (a glyph, not a blank or a full fill); `tile`:
  `coverage` ≈ 0.95 (the rounded tile); `#rrggbb`: `coverage` = 1.
- **Colour** — vision: the glyph is the asked colour (white on a tile).
- **License** — the `LICENSE:` line names a license and an SPDX id; a
  `lookup failed` line means you look the set up by hand before delivering.
- **Brand mark** — a `simple-icons:*` id is reported with the trademark
  caveat: refers to the brand, not altered, no endorsement implied.

A failed check is one rerun (a transient API error) or a `Q<n>:` /
reported gap; it is never silently delivered.

</QA>

<Report>

`source-icon` + the background used; the svg and png at their absolute
paths; each QA check with its evidence (the `RESULT:` numbers and the
vision verdict); the `LICENSE:` line verbatim; `spend: free`; anything
Creator must decide (a search's candidates).

</Report>
