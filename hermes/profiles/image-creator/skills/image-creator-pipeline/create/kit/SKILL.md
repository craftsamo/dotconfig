---
name: create-kit
description: >-
  A deterministic game-UI KIT — buttons, panels, bars — drawn as flat-vector
  or pixel art (never generated, never a website/React component set).
  Source SVG + transparent PNG per item/state in category folders,
  a manifest.json and a slices.json (9-slice borders in final output
  pixels) for the stretchable pieces. Zero spend; the same options
  reproduce the same bytes.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [kit, ui, game-ui, buttons, panels, bars, deterministic, free]
    category: hands
    hands: image-creator
    cost: free
    output: "assets/<category>/<slug>_<name>[_<state>].svg + .png, manifest.json, slices.json"
    form:
      contents:
        required: true
        type: text
        label: "comma list, subset of: buttons, panels, bars — a world-prop or icon-set request is not this leaf (route generate-kit / source-kit, never omit silently)"
        example: "buttons,panels,bars"
      style:
        required: true
        options: [flat-vector, pixel]
        label: "the two supported looks — closed set, no other style is drawn here"
      palette:
        required: false
        label: "three #rrggbb roles, surface,ink,accent (default #243246,#f3f5ff,#f8b84e)"
        example: "#1c1f26,#f2f2f2,#5ac8fa"
      radius:
        required: false
        type: int
        label: "corner radius in logical px (default 12 flat-vector / 0 pixel); rejected if it does not fit the smallest requested category, never silently clamped when given explicitly"
      stroke:
        required: false
        type: int
        label: "border width in logical px (default 2 flat-vector / 1 pixel); same fit rule as radius"
      size:
        required: false
        type: int
        label: "integer output scale, 1-4 (default 1). flat-vector: expands the SVG canvas coordinates; pixel: nearest-neighbour upscale of the tiny logical bitmap — never a smoothing filter"
      states:
        required: false
        type: text
        label: "comma list, subset of: normal, pressed, hover, disabled (default normal,pressed). Applies to buttons only — panels and bars render one file per item"
        example: "normal,pressed,hover,disabled"
      items:
        required: false
        type: file
        label: "optional JSON override of the default items per category ({\"buttons\":[\"primary\",\"secondary\",\"cancel\"]}); omit unless the default items (buttons: primary+secondary, panels: window+tooltip, bars: frame+fill) do not fit the brief. A name outside the defaults (e.g. \"cancel\") is NOT a bespoke design — it renders with a generic fallback role and the same geometry as its category's other items, flagged custom_name in the manifest. If the brief implies a genuinely different look per custom name, that is a scope question — ask, don't ship a look-alike as if it were bespoke"
      slug:
        required: false
        label: "file-name stem (default kit); a-z 0-9 and internal hyphens only"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm this is a KIT request — reusable UI chrome (buttons/panels/bars),
   not a single icon, a world/environment prop, or a generative image. A
   world-prop or icon-set ask routes to `generate-kit` / `source-kit`
   instead; never fold it into this leaf's output silently.
2. Render:

   ```
   python3 ${HERMES_SKILL_DIR}/scripts/ui-draw.py --out <deliver> \
     --contents <contents> --style flat-vector|pixel \
     [--palette '#surface,#ink,#accent'] [--radius N] [--stroke N] \
     [--scale <size>] [--states normal,pressed[,hover,disabled]] \
     [--slug <slug>] [--items <items.json>]
   ```

   Always through `python3` — never rely on the file's own execute bit.
   It prints one `RESULT:` line (files + slices counts) and writes
   `manifest.json` + `slices.json` under `<deliver>`. The output directory
   must not already exist and be non-empty — the script builds atomically
   into a temp dir and moves it into place, so a half-built kit never lands
   as `<deliver>`. `--style flat-vector` requires `rsvg-convert` on PATH
   (`./install.sh --deps` for librsvg) and refuses to run without it — see
   the QA note below; `--style pixel` has no such requirement.
3. Build the atlas and run measurement through the shared image helper on
   the rendered assets (never on `<deliver>` whole — that also contains
   `manifest.json`/`slices.json`, which are not images) and never
   re-implement atlas/measure locally:

   ```
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py atlas <deliver>/assets <deliver>/atlas
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py measure <deliver>/assets --out <deliver>/qa
   ```

   `qa` sits beside `assets`, not nested inside it.
4. Look at the atlas once per style/state group: for `flat-vector`, geometry
   is identical across `normal`/`pressed`/`hover`/`disabled` and only the
   fill colour changes; for `pixel`, corners are stepped, not smoothed, and
   every block of `size × size` output pixels is one flat colour (zoom in).
5. Prove the promised `slices.json` contract — this is REQUIRED, not an
   optional nicety, because it is a delivered file another engine will
   trust verbatim. Pick one stretchable PNG (a button or the panel
   `window`) and its `slices.json` entry, run a real 9-slice expansion with
   ImageMagick (crop the four corners unstretched, resize the four edges
   along one axis, resize the centre both axes, recompose at 2× the
   original box), then diff the four corner crops of the result against
   the four corner crops of the original — `magick compare -metric AE`
   must report `0` differing pixels. If the picked PNG is the panel
   `window`, ALSO measure its title bar's pixel height (the vertical run
   of accent colour down one interior column) before and after — it must
   be identical; `window`'s `top` slice is driven by the title bar's own
   bottom edge, not the generic corner radius, and a check that skipped
   this would miss the one panel item where the generic inset alone is
   not enough. Report both counts; a check that was never run is not
   evidence.
6. `intent: revise` — rerun with the changed option; the same arguments
   reproduce the same bytes (verify with a checksum if in doubt).

</Procedure>

<QA>

Every check with its evidence:

- **Contents/style honoured** — `RESULT:` and `manifest.json` list exactly
  the requested categories, items and states (buttons only) at the
  documented logical sizes for the chosen style.
- **Determinism** — rerunning the same command against a fresh
  `--out` produces byte-identical files (`diff -rq` the two directories).
- **Alpha** — `magick identify -format '%[channels]'` on a rounded item
  shows an alpha channel; a corner pixel reads `alpha=0`
  (`magick identify -format '%[pixel:p{0,0}]' file.png`), the shape's
  centre reads full alpha.
- **Pixel style crispness** — zoom into a scaled pixel PNG: no
  intermediate/antialiased colour inside a `size × size` block, no smooth
  curve at a rounded corner.
- **State colours, fixed geometry** — for buttons, `pressed`/`hover`/
  `disabled` are visibly darker/lighter/desaturated than `normal` at the
  same crop, with the identical silhouette (same width/height, same
  radius).
- **Bars share one box** — a bar's `frame` and `fill` report the same
  width/height in the manifest; `fill` never overlaps `frame`'s stroke.
  The inset beyond the stroke is per style, not a shared number:
  flat-vector keeps a visible 2px (logical) gap; pixel's fill starts
  exactly where the stroke ends (no extra gap — a pixel bar is only 8px
  logical tall, so a flat-vector-sized gap would leave a 25%-height
  sliver instead of 75%). Check the fill's opaque height is a clear
  majority of the canvas for pixel, not that a gap exists.
- **Slices** — every `slices.json` entry's `left+right < width` and
  `top+bottom < height` STRICTLY (a geometry that would leave a zero or
  negative centre band is rejected up front by the script, never
  silently clamped — a slices.json entry that failed this would mean the
  reject guard itself has a bug); `bars`' `fill` never appears in
  `slices.json`. Panels' `window` gets its OWN `top` — `max(generic
  corner inset, title bar's own bottom edge)` — because the title bar
  reaches past the generic corner radius; a geometry that would leave no
  room under it is rejected the same way (`tooltip` always uses the
  plain generic inset on every side).
- **9-slice proof (required, step 5)** — the `magick compare -metric AE`
  count between the original and expanded corner crops is `0`, AND (for a
  `window`) the title bar's own pixel height is unchanged after the
  expansion. This is not an optional nicety: report both counts, not
  "looks fine".
- **Custom item names, never silent** — if `--items` introduced a name
  outside the category's defaults, `RESULT:` printed `custom_names=` and
  every such manifest entry carries `"custom_name": true`; a request that
  actually wanted a distinct bespoke look per custom name is a finding
  for Creator, not something this leaf renders on its own.
- **`flat-vector` never runs without `rsvg-convert`** — a missing
  dependency is `ui-draw: rsvg-convert (librsvg) not found — required for
  --style flat-vector; run ./install.sh --deps` on stderr and a non-zero
  exit, never a silent lower-fidelity render. (ImageMagick's own built-in
  SVG delegate does not reliably render an unfilled, `fill="none"` stroked
  shape — confirmed directly, a bars `frame` came out fully transparent —
  so there is no safe fallback path for this style; `pixel` never touches
  an SVG renderer and is unaffected.)

A failed check is a rerun with the option that fixes it (free) or a
finding for Creator — never a silent delivery.

</QA>

<Report>

`create-kit` + style + contents; the options used (palette, radius,
stroke, size, states, items override if any); the delivered directory,
`manifest.json`/`slices.json` paths and the atlas/qa paths; each QA check
with its evidence, including the step-5 9-slice AE count; `spend: free`;
anything Creator must decide (a world-prop request that does not belong
in this leaf, a radius/stroke rejected for not fitting a requested
category, a custom item name that implied a bespoke look this leaf does
not draw).

</Report>
