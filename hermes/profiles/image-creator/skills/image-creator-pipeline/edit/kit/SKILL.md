---
name: edit-kit
description: >-
  Deterministically finish or package an existing game props/UI kit:
  cutout, rectangular contain-fit, pixel-grid resampling, shared-palette
  remap, or a native-size PNG atlas with coordinates. No new drawing,
  no invented states, no web components; geometry/style changes go to
  create-kit or generate-kit. Source assets are never overwritten. Free.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [kit, edit, atlas, palette, free]
    category: hands
    hands: image-creator
    cost: free
    output: "assets/ PNGs preserving category paths, manifest.json, optional atlas/atlas.png + atlas.json, qa/ and kit.zip"
    form:
      source:
        required: true
        type: path
        label: "one PNG or the assets directory of an existing kit; not a whole delivery containing raw files and preview sheets"
      operation:
        required: true
        options: [fit, palette, atlas]
        label: "fit transforms size/cutout; palette remaps onto a supplied swatch strip; atlas preserves every source pixel"
      canvas:
        required: false
        type: text
        label: "fit only: WxH for this subset, or original to retain each source canvas size (default original); split mixed categories when target sizes differ"
      pixel:
        required: false
        options: ['yes', 'no']
        label: "fit/palette: yes means nearest-neighbour and binary alpha (default no); canvas is the native logical grid, not an arbitrary smooth upscale"
      cutout:
        required: false
        options: [auto, 'yes', 'no', key]
        label: "fit only, default no for an existing kit; yes corner flood, key global corner-colour removal"
      fuzz:
        required: false
        type: int
        label: "cutout tolerance percent, 0-100 (default 10)"
      pad:
        required: false
        type: text
        label: "fit inset fraction 0 <= pad < 0.5 (default 0); matching canvas size does not preserve pivots after trim/fit"
      palette:
        required: false
        type: image
        label: "palette operation: fixed opaque swatch-strip PNG, required; a full mood board is not a palette"
      columns:
        required: false
        type: int
        label: "atlas columns (default 4); full size frames, transparent gaps, max 4096px canvas; split categories if too large"
      gap:
        required: false
        type: int
        label: "atlas transparent padding in px (default 2), not edge extrusion or mipmap bleed protection"
      note:
        required: false
        type: text
---

<Procedure>

1. Inventory only the requested assets. Reject missing sources, duplicate
   intended output paths, or `<deliver>` inside the source directory.
   For each PNG record category/relative path and measured canvas. Ask
   once for missing operation-specific inputs, including a palette for
   `operation: palette`. Do not silently flatten all categories to one
   square. Reject options irrelevant to the selected operation rather
   than accepting a palette, cutout or resize on a lossless atlas request.
2. Use a fresh delivery per revision. Copy originals preserving relative
   paths into `<deliver>/assets` for atlas-only work. For fit/palette,
   write a batch script under `<deliver>/finish.sh` using these calls:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py fit <source-file> <deliver>/assets/<relative-file> --canvas <WxH> --cutout <cutout> --pad <pad> [--fuzz N] [--pixel] [--palette <palette>]
   ```

   `fit` trims and contains: it changes registration, even at the same
   canvas size. Do not re-fit a state/frame/fill group without checking
   their shared pivots. For palette-only edits, preserve geometry using
   `magick <source> -alpha extract <mask>` then
   `magick <source> -alpha off +dither -remap <palette> <mask> -alpha off
   -compose CopyOpacity -composite -strip <output>` in the batch script;
   threshold the mask at 50% only when `pixel: yes`. Do not trim or fit
   merely to recolour. Text commands belong in script files, not inline
   loops. Each skill-script invocation is its own terminal command;
   long terminal batches use `background: true` with polling.
3. For `atlas`, run:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py atlas <deliver>/assets <deliver>/atlas --columns <columns> --gap <gap>
   ```

   This is a grid, not an optimal bin packer or a game-engine importer.
   Frames are full, untrimmed sources; `atlas.json` uses relative names
   and top-left pixel coordinates. Max 64 files and 4096px/16Mpx canvas;
   split category subsets into separately named atlases if needed, never
   downscale silently. Inherit any input `slices.json` only when pixels
   were unchanged; transformations invalidate it unless recomputed and
   tested. Do not invent slice borders by looking at an image.
4. Measure the asset directory with
   `python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py measure
   <deliver>/assets --out <deliver>/qa [--palette <palette>]`.
   Over 64 files: measure category subsets into distinct QA directories.
   Helper output dirs must be empty; use fresh names after a correction,
   never reuse stale sheets. Inspect the contact sheet, light/dark edges,
   state/frame/fill alignment and pixel grids. Append findings to `qa.md`
   after every look before vision's next image replaces the context.
5. Write `manifest.json` with source path, output relative path, operation,
   dimensions, bytes and `passed`/finding for every requested asset.
   Copy source license/provenance documents into the delivery unchanged.
   Zip assets, manifest, provenance and atlas if requested, retaining
   folders. Do not copy a source engine manifest as if transformed
   coordinates were still valid.

</Procedure>

<QA>

- Requested count and relative paths match, including duplicate basenames
  in different categories. No source bytes changed.
- Fit: exact target canvas, aspect preserved, nonempty alpha, no fringe,
  silhouettes and state registration still usable.
- Palette: no new opaque colours outside the supplied strip; source
  alpha preserved unless binary alpha was explicitly requested. Similar
  palette does not prove perceptual consistency.
- Atlas: frame width/height match source; crop frames using atlas.json
  and compare decoded pixels, including alpha (`magick compare -metric
  AE` must be zero). Transparent gaps are not extrusion.
- Every output gets a verdict; unknown original slice/pivot data is a GAP
  after a geometry edit, never silently declared preserved.

</QA>

<Report>

`edit-kit` + operation; assets/manifest/atlas/zip paths; count and checks
with measurements and recorded visual evidence; invalidated slice/pivot
metadata; failed files and next action; `spend: free (no image generation)`.

</Report>
