---
name: generate-kit
description: >-
  A game props and UI asset kit in one visual language: world props,
  icon sets, buttons, panels and bars, in pixel art, 3D-rendered,
  cel-shaded, hand-painted, flat-vector or a described style. Two rounds:
  three style-sheet candidates, then individual transparent PNG assets
  on the approved sheet. UI states are named items. Not a functional web
  component library, 3D models or engine-ready UI code. For exact SVG
  geometry and 9-slice borders use create-kit; for existing packs use
  source-kit. Metered.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [kit, game, props, ui, image_gen, metered]
    category: hands
    hands: image-creator
    cost: metered
    output: "A: anchor/anchor_v<N>.png + sheet.png, design-lock.md, items.json, qa.md; B: assets/<category>/<item>.png + manifest.json, qa/, kit.zip"
    form:
      what_for:
        required: true
        type: text
        label: "what is in the kit and what it is for: world, theme, objects, mood and intended screen or game"
        example: "A cosy forest alchemist game: bottles, crates, crafting inventory and warm wooden HUD"
      style:
        required: true
        options: [pixel, 3d-render, cel-shaded, hand-painted, flat-vector]
        other: true
        label: "a listed look or a described one; 3d-render means 2D pictures of rendered objects, not model files"
      contents:
        required: true
        type: text
        options: [world-props, icon-set, buttons, panels, bars]
        other: true
        label: "comma-separated categories (multiple allowed), or describe a custom set; references/contents/<category>.md gives suggested items, not mandatory additions"
        example: "world-props,buttons,bars"
      items:
        required: false
        type: text
        label: "one category/item: description per line; when present this IS the complete list, replacing category defaults; name states separately, e.g. buttons/primary-normal and buttons/primary-pressed"
        example: "world-props/crate: wooden supply crate\nbuttons/primary-normal: idle wooden button\nbuttons/primary-pressed: the same button pressed"
      perspective:
        required: false
        options: [side, top-down, isometric, front]
        label: "world-prop camera; defaults to side; UI always faces the screen without perspective distortion"
      palette:
        required: false
        type: text
        label: "two to four dominant colours, as hex or words; pixel colours are locked to one shared swatch strip"
      reference:
        required: false
        type: image
        label: "mood board, existing game screen or brand reference; confirm permission to send it to the configured image backend"
      anchor:
        required: false
        type: image
        label: "approved style sheet; absent = candidates only, present = batch on the approved items and design lock"
      size:
        required: false
        type: int
        label: "integer output scale 1-4 (default 1) over the category's native canvas; pixel uses nearest-neighbour enlargement"
      slug:
        required: false
        label: "archive stem, lowercase hyphenated slug (default kit)"
      note:
        required: false
        type: text
---

<Procedure>

1. Resolve the form before spending. Load `references/styles/<style>.md`
   for a listed style; for a described one write `style.md` in the same
   Look / Prompt block / Avoid / QA cues shape. Treat `contents` as a
   comma-list, not a single option. Read each selected
   `references/contents/<category>.md`. Use its table only when `items`
   is absent; otherwise parse the explicit list without adding defaults.
   For custom categories agree descriptions and canvas sizes with Creator.
   Require unique `category/item` slugs, at least two items, size 1-4,
   and exactly the requested categories. Unknown sizes or an unusable
   reference produce one `Q<n>:` block, not a guessed batch.
2. Write `<deliver>/items.json` as an array of `{category,item,description,
   width,height,state}`. Dimensions are the final output pixels: the
   content table's native size times `size`. `state` is `normal`,
   `pressed`, `hover`, `disabled` or `static`; state variants are separate
   rows. Write `<deliver>/design-lock.md`: palette, line weight, material,
   lighting, world camera, front-facing UI, corner shape, spacing, native
   pixel grid when relevant, and exclusions. No global Style registry.
   Inspect a supplied reference once and record which qualities carry
   over, not its background. Persist the findings to `qa.md` immediately.

**Round A: no anchor, candidates only.**

3. Select one representative item from each requested category. Compose
   one style-sheet prompt with those separate, clearly spaced objects
   on a plain neutral ground, no captions, text, watermark or background
   scene. State the medium explicitly (a sprite sheet, painted game
   assets, cel-shaded drawings, or rendered-object pictures), not merely
   an adjective. Save the prompt in `anchor/prompt.txt` before calling
   `image_generate`. A sheet is a visual direction sample, NOT a texture
   atlas to cut apart into deliverables.
4. Generate three candidates by default, or the smaller explicit budget.
   Call `image_generate(prompt, aspect_ratio="square")` once per candidate;
   when a reference was approved for upload, also pass
   `reference_image_urls=[<reference>]`. If the tool does not expose that
   parameter, stop rather than silently ignoring the reference. Keep the
   originals under `anchor/raw/` and localize returned URLs promptly.
   Normalize whole sheets, without cutout or trimming:

   ```sh
   bash ${HERMES_SKILL_DIR}/../../scripts/img-postprocess.sh <raw> <deliver>/anchor/anchor_v<N>.png --size 1024x1024 --fit contain --format png
   ```

   Record backend and every attempted call, including failures, in
   `anchor/prompt.txt`. Retries consume the budget too.
5. Assemble a contact sheet with `magick <candidates> -resize 256x256
   +append <deliver>/anchor/sheet.png`. Inspect this and the recommended
   candidate at native size. Check that props and UI belong to the same
   kit but the UI is not tilted like the world props. After EACH look
   append the named findings to `qa.md`; vision retains about three
   images. Return candidates, recommendation, expanded item count and
   Round B call allowance. STOP. Approval comes back through Creator as
   `intent: revise <dir>` with `anchor: <approved image>`; never choose
   your own anchor and continue.

**Round B: approved anchor and item list.**

6. Read the approved `items.json` and `design-lock.md` from the prior
   delivery. If the client supplied an external anchor, first settle and
   record those two documents; do not infer approval of an unseen list.
   Any changed items require count and budget reconfirmation. Allow
   one call per item plus `ceil(n/4)` corrective calls unless a smaller
   explicit budget applies. More than 24 items requires an explicit
   `budget:` line. If the allowance cannot cover the requested items,
   return a question before generation; do not silently produce a subset.
7. For each item, write its full prompt under `prompts/<category>/`:
   the locked medium and design, exact item/state description, one
   isolated asset, no text, no watermark, no drawn checkerboard, no
   floor shadow, generous margin, flat chroma colour absent from the
   object. Pass `reference_image_urls=[<anchor>]` to `image_generate`;
   the anchor controls STYLE, not a command to redraw the whole sheet.
   Use the category's canvas aspect as guidance. Keep each raw under
   `raw/<category>/<item>.<ext>`. Save progress and spend after each item.
   Image tool calls run individually; only long terminal batch scripts
   use `background: true` and polling. Never add nonexistent background
   parameters to `image_generate`.
8. Finish one asset at a time, never a generated sheet:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py fit <raw> <deliver>/assets/<category>/<item>.png --canvas <WxH> --cutout auto --pad 0.04
   ```

   Local finishing does not consume image-call budget: "no retries" on
   the generation grant does not prohibit a free re-finish of saved raws.
   Correct a fringe or swallowed edge with `--fuzz N` first. Background
   trapped in pockets may need `--cutout key`; inspect the alpha afterward.
   The forest-kit smoke run kept a magenta fringe at fuzz 10 despite
   `key_px=0`; re-finishing the SAME raws with `--cutout key --fuzz 30`
   removed it without another image call. Check native edges, not only
   the contact sheet or key-colour count. Do not increase fuzz repeatedly
   without looking: a colour also present in the object can be erased.
   Non-pixel canvases use final dimensions. For pixel, finish to the
   NATIVE grid under `<deliver>/native/<category>/` with `--pixel`,
   never alongside final files in assets. Then enlarge by integer `size`
   using `magick <native> -filter point -resize <size*100>% -strip <final>`.
   Lock a shared palette from the first approved, clean cutout via
   `kit-images.py palette <cutout> <deliver>/palette.png --colors 16`, or
   make a swatch strip from the agreed hex values; re-finish every item
   with `--palette <deliver>/palette.png`. Never extract colours from the
   opaque anchor's neutral background. Quantization is not proof of good
   pixel art: inspect grid clusters and silhouettes.
9. Run `python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py measure
   <deliver>/assets --out <deliver>/qa --against <anchor>` (plus
   `--palette <palette.png>` for pixel). The helper rejects over 64 files:
   measure category subdirectories separately with distinct QA dirs for
   larger kits. Inspect `sheet.png`, `light.png`/`dark.png` for alpha,
   and individual native-size files for small UI or questionable edges.
   Magnify native pixel assets 4x with the point filter to judge them.
   Write each finding to root `qa.md` before the next look.
10. Check every requested item/state against the lock. Generating two
    states independently does NOT guarantee matching silhouettes; flag
    shifted borders, pivots or content regions and use one corrective
    within budget, or recommend `create-kit` for exact geometry. Do not
    call these images 9-slice-ready or engine-ready without evidence.
    Reroll only the failed item, at most once; never reroll the whole kit.
    After any corrective or free re-finish, measure into a fresh
    `qa-v<N>/` and inspect the changed assets; existing QA directories
    are refused to prevent stale sheets. Point the final report and
    manifest at the latest measurements, retaining earlier QA as history.
11. Write `manifest.json` with every `items.json` row plus relative `file`,
    measured `bytes`, `passed` and a concrete `finding`. Retain failed
    items with `passed:false`; missing output gets `file:null`, not a
    fabricated path. Package assets, manifest, design lock and QA with
    `zip -r` from the delivery directory, excluding raw/prompt files and
    the archive itself. Preserve category folders (never `zip -j`).
    An atlas is an optional `edit-kit` request, not a generated sheet.

</Procedure>

<QA>

- **Coverage**: item/category/state counts match the approved list; no
  extra defaults, missing files or duplicate identifiers hidden by a zip.
- **Style**: named cues from the selected reference; palette, outline,
  light direction and materials agree across props and UI. Report drift
  per file, not "consistent" based only on a similar average colour.
- **Use size**: actual target-size props have distinct silhouettes;
  button borders and bar fills remain readable. UI faces the screen;
  the prop camera matches `perspective`.
- **Alpha/geometry**: measured canvas equals the item row, nonempty alpha,
  no chroma residue, holes, clipped shadows or backgrounds. UI may fill
  its canvas; do not impose mascot coverage thresholds on a panel.
- **States**: normal/pressed pairs keep the same silhouette and alignment;
  generated drift is a FAIL, not dismissed as artistic variation.
- **Pixel**: binary alpha, one palette and native grid, integer final scale;
  inspect clusters, not only a colour count.
- **Budget**: every attempt counted, no batch without anchor/list approval,
  remaining failures visible in both the manifest and report.
- Extra RGB/alpha/native-vs-final checks (at most 16 opaque colours across
  the kit, all in the shared palette; binary alpha; aligned size-by-size
  RGBA blocks against the source native images outside `assets/`) belong
  in `<deliver>/verify-pixels.py`, run as
  `python3 <path>`, not inline `python3 -c` or inline loops, which the
  terminal guard can block. A composite QA preview must reset gravity to
  northwest before crop/append, or a prior south gravity crops the panel.

</QA>

<Report>

`generate-kit` + round + style + categories + item count. A: candidate and
sheet paths, recommendation with findings, expanded list, proposed call
allowance and the approval needed. B: assets, manifest, QA and zip paths,
failed/missing items and repair route. State which backend received any
reference upload. Include `spend: img <attempts>/<allowance>`; do not call
an unverified kit production-ready.

</Report>
