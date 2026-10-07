---
name: source-icon
description: >-
  One published icon fetched from the open icon libraries on the Iconify
  API (Lucide, Tabler, Phosphor, Material Symbols, Simple Icons brand
  marks, … 200k+ glyphs, no key) as the source SVG plus a PNG in the asked
  colour, size and background with its license recorded, or a vendor's own
  official logo file delivered unmodified with source URL, hashes and
  usage terms. Nothing is drawn or generated. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [icon, iconify, svg, png, source, brand, logo, free]
    category: hands
    hands: image-creator
    cost: free
    output: "Iconify: icon_<slug>.svg + icon_<slug>_<size>.png (default 512) + a LICENSE line; official: the vendor file(s) unmodified + provenance.json + terms.txt"
    form:
      icon:
        required: false
        label: "Iconify id `set:name`, or a search word when the id is unknown; omit when official is yes"
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
      official:
        required: false
        label: "yes = the vendor's own logo file from its brand page or press kit, unmodified, with source URL and usage terms (default no: Iconify)"
      vendor:
        required: false
        label: "company or product whose official mark is wanted (needed when official is yes)"
        example: "xAI Grok"
      variant:
        required: false
        label: "official: glyph (logomark, default) | lockup (glyph + wordmark) | wordmark"
      backdrop:
        required: false
        label: "official: the destination background, light | dark (picks the dark-ink or light-ink file)"
      slug:
        required: false
        label: "filename stem (default: the id with `:` → `-`)"
      note:
        required: false
        type: text
---

<Procedure>

**Iconify path** (`official` absent or no; `icon` is required here — a
missing `icon` is `Q1:`).

1. If `icon` is a WORD rather than a `set:name` id, run
   `${HERMES_SKILL_DIR}/scripts/icon-fetch.sh --search <word>` and return
   the `CANDIDATES:` list as `Q1:` with your recommendation (glyph choice is
   the Assistant's, not yours). Stop there.
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

**Official path** (`official: yes`; `vendor` is required — a missing one is
`Q1:`). The mark is sourced, never drawn: never redraw, trace, recolour,
crop, round or generate a lookalike, and never deliver an approximation.

1. Read `skill_view(name="source-icon", file_path="references/vendor-findings.md")`
   first; a recent row settles the source or that none exists.
2. Aggregators: `simple-icons` through this leaf's Iconify path and the
   svgl catalogue (`https://api.svgl.app?search=<vendor>`) are normalized
   redistributions, fine for a quick nominative glyph but not the vendor's
   own file; say which you used. When the form asks for the vendor's own
   file, or the aggregators miss or look stale, go to step 3.
3. The vendor's brand page: try `/brand`, `/brand-guidelines`,
   `/legal/brand-guidelines`, `/press`, `/newsroom`, `/media-kit`. Read it for
   BOTH the download link and the usage terms. A brand page is not proof an
   SVG exists: list the download's contents before claiming one (partnership
   templates, PNG-only kits and login-gated portals are common dead ends).
4. Download unmodified into a scratch directory under `deliver`. A curl 403
   is bot protection, not absence: follow
   `skill_view(name="source-icon", file_path="references/fetching-gated-brand-pages.md")`
   (a real `.mjs` file, never an inline script; each command on its own).
5. Pick the file for `variant` and `backdrop` (dark-ink for a light background,
   light-ink for a dark one) and copy it into `deliver` byte for byte.
6. Write the usage-terms summary (nominative use, no alteration, revocable,
   prominence clauses) to `deliver/terms.txt`, then run each in a command of
   its own:

   ```
   ${HERMES_SKILL_DIR}/scripts/brand-check.py render <deliver>/<file>.svg
   ${HERMES_SKILL_DIR}/scripts/brand-check.py provenance --file <deliver>/<file>.svg \
     --source-url <url> [--archive <scratch>/<kit>.zip --member <path in zip>] \
     --terms <deliver>/terms.txt --out <deliver>/provenance.json
   ```

7. No official mark is distributed: stop and report it with the evidence. A
   text wordmark is the user's decision and not this leaf's output.

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

Official path:

- **Parses, viewBox, renders** — `brand-check.py render` PASS for every
  delivered SVG (a valid file can still render blank).
- **Provenance** — `provenance.json` exists: file sha256, source URL, and for a
  kit the archive sha256, a clean archive test and `identical_to_member`.
- **Variant** — vision on the render: the asked glyph / lockup / wordmark, the
  ink suited to `backdrop`.
- **Terms** — `terms.txt` summarises the vendor's usage terms; the trademark
  caveat is reported.

A failed check is one rerun (a transient API error) or a `Q<n>:` /
reported gap; it is never silently delivered.

</QA>

<Report>

`source-icon` + the background used; the svg and png at their absolute
paths; each QA check with its evidence (the `RESULT:` numbers and the
vision verdict); the `LICENSE:` line verbatim; `spend: free`; anything
the Assistant must decide (a search's candidates). Official path: the
delivered files, `provenance.json`, the terms summary and which source was
used (vendor file or aggregator), or the evidence that no official mark
exists; a vendor finding not yet in `vendor-findings.md` is reported for the
maintainer, never written into the skill tree.

</Report>
