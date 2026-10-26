---
name: analyze-kit
description: >-
  Inspect an existing game props/UI kit without redrawing it: inventory,
  dimensions, alpha, palette and style coherence, use-size readability,
  button-state alignment and bar frame/fill registration. Returns a
  PASS/WARN/FAIL/GAP findings table with evidence and repair routes.
  Not a web accessibility audit, engine importer or asset generator. Free.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [kit, analyze, consistency, alpha, free]
    category: hands
    hands: image-creator
    cost: free
    output: "qa.md findings + measurements.json and review sheets; original assets unchanged"
    form:
      source:
        required: true
        type: path
        label: "PNG asset directory or one PNG, excluding raw images, atlases and review sheets"
      against:
        required: false
        type: image
        label: "approved style sheet or anchor to compare against"
      palette:
        required: false
        type: image
        label: "fixed opaque palette-strip PNG, optional; no palette-distance claim without one"
      manifest:
        required: false
        type: file
        label: "expected item list or delivered manifest with category, item, dimensions and state; absent means completeness/spec checks are GAP"
      note:
        required: false
        type: text
---

<Procedure>

1. Inventory the requested PNGs, excluding previews and raw versions by
   choosing the correct source directory, not by silently dropping files.
   SVG-only assets need separate raster review; state that limitation.
   Compare the requested list/manifest if supplied; do not let an empty
   set pass. Do not modify or re-finish any source image.
2. Choose a fresh `<deliver>` outside `source`. If absent, use a temporary
   analysis directory and report its path. Run:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py measure <source> --out <deliver>/qa [--against <against>] [--palette <palette>]
   ```

   The helper produces measurements.json plus sheet.png, native.png,
   light.png, dark.png, silhouette.png and optional against.png. No
   numeric measurement is an automatic PASS. More than 64 files requires
   category subsets, each into its own QA dir, with an aggregate count;
   never show only the first subset as if it covered the whole kit.
3. Read the measurements: exact canvases against manifest, empty alpha,
   clipped bounds, colour differences. Full coverage can be valid for a
   panel. For a flat requested swatch strip, report nearest opaque colour
   distances; do not treat gradients or painted highlights as a failure
   merely because their distance is nonzero. An opaque style sheet's
   background is not part of the kit palette.
4. Inspect contact, light/dark and silhouette sheets. Compare actual
   native files at intended display size for borders, controls and prop
   silhouettes; `native.png` contains only the first file, NOT evidence
   for all items. For small pixel assets, point-magnify the original 4x.
   Open additional questionable files individually. Write a finding to
   `qa.md` immediately after EACH look; vision retains about three images.
5. For each normal/pressed pair compare canvas, contour and content
   placement. For bars overlay fill on frame: colour must sit within the
   inner frame and both must have the same registration. Without stated
   pair mappings, request them or mark this check GAP, not PASS by name
   guessing. Check slice borders only when provided and verified through
   an actual expansion; do not infer engine readiness from a screenshot.
6. Return a findings table: `check | file/set | evidence | verdict |
   repair`. Verdicts are PASS, WARN, FAIL or GAP. Cite measured values or
   the specific inspected file/cue, not "looks consistent". Routes:
   cutout/size/palette/packing to `edit-kit`; exact UI state geometry to
   `create-kit`; redrawing/style repair to `generate-kit`; missing stock
   pieces to `source-kit`. No repair runs as part of analysis.

</Procedure>

<QA>

- Every requested file is counted; missing items and unsupported SVG-only
  review appear explicitly, with no claims for uninspected subsets.
- Measurements and visual findings are kept distinct. A palette match
  alone does not certify a style; shared dimensions do not certify pivots.
- Every PASS has observable evidence; missing spec/anchor produces GAP
  for those comparisons, not invented expectations.
- Source files remain byte-identical and no image generation is called.

</QA>

<Report>

`analyze-kit`; total files and categories, findings table ordered FAIL,
GAP, WARN, PASS; paths to measurements and QA sheets, each unresolved
decision and the appropriate leaf; `spend: free (inspection only)`.

</Report>
