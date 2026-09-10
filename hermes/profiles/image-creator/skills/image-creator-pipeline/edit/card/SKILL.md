---
name: edit-card
description: >-
  Adapt an existing finished raster CARD to a destination by explicit
  cover/contain/pad/focus, optionally adding an exact-text band. Protect requested
  content from destructive cropping. No generation or semantic redraw; revising
  an owned source spec should rerender create-card instead of cropping its text.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [card, edit, crop, contain, typography, free]
    category: hands
    hands: image-creator
    cost: free
    output: "master.png + ordered tiles + preview.png + manifest.json + spec.json; optional band HTML/layout evidence"
    form:
      source:
        required: true
        type: image
        label: "absolute existing PNG/JPEG/WebP; finished image, not a generated-art request"
      destination:
        required: true
        label: "create-card destination name or explicit WxH; one destination per run"
      fit:
        required: true
        options: [cover, contain, pad, focus]
        label: "explicit adaptation: contain recommended to preserve text; pad never scales"
      focus:
        required: false
        type: text
        label: "normalized JSON [x,y] crop center, required ONLY with fit=focus"
      protected:
        required: false
        type: text
        label: "JSON list of source-pixel [x,y,w,h] rectangles; hands resolve any user-named must-keep content into these before cropping"
      title:
        required: false
        type: text
        label: "exact new copy for a separate bottom text band; not replacement of source lettering"
      text_band:
        required: false
        type: int
        label: "band height in pixels, positive and at most half canvas; requires title; single card only"
      font:
        required: false
        type: file
        label: "optional band font file"
      tiles:
        required: false
        type: int
        label: "pair=2; carousel=3|4; explicit adaptation of one source panorama"
      tile:
        required: false
        label: "carousel portrait 4:5 (default)|square 1:1|tall 1:2; pair candidate (unverified)"
      gap:
        required: false
        type: int
        label: "legacy source-image-px gap 0..128, default 16; separate carousel display preview uses canonical CSS-px width/gap"
      slug:
        required: false
        type: text
      note:
        required: false
        type: text
---

<Procedure>

1. Load `skill_view("create-card")` for the selected destination, then its
   linked file-based execution contract. An owned
   previous create spec needing changed copy/layout is `intent: revise` on
   create-card into a fresh bundle, not a global crop of text-bearing pixels.
   A finished image alone cannot restore missing source layers.
2. Look once at the source at native size; identify requested protected text,
   faces, logos and mandatory content. Persist that finding before the next
   look. Convert requested must-keep areas into source-pixel rectangles. If
   boundaries cannot be confidently established, ask Creator or use approved
   contain/pad; never treat absent rectangles as crop permission. Cover/focus
   may remove edges; contain fits over cream padding; pad preserves scale.
3. Write JSON from the form (decode focus/protected text into concrete arrays).
   Run as its own command, copy never in argv:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/card.py edit <absolute-spec.json> --out <new-absolute-bundle>
   ```

   The output must not exist. The helper rejects conflicting options and crops
   intersecting protected rectangles. Report rejection or obtain a changed fit,
   never drop protected rectangles to force a pass. A title band reserves space
   BELOW the fitted source; it does not paint over existing content. For tiled
   lettering rerender the owned create spec, not an unsupported band workaround.
4. Review result at native and reduced size per delivered tile (360px wide,
   youtube-thumb 168px); add one carousel simulated-display.png overview with
   its CSS-px JSON label (pair: legacy gap preview). Write each
   verdict into qa.md immediately. One corrective free rerun into a new bundle
   for a specific fit defect; otherwise surface the finding. No generation.

</Procedure>

<QA>

Report actual canvas, scaled crop coordinates, protected-rectangle count and
tile reassembly equality from manifest. Compare protected source content and
exact band text visually, separate from measurements. No cut words, lost
requested faces/logo, stretched source geometry or text crossing a tile seam.
If finished source text crosses requested tile boundaries, reject or surface
the finding; splitting pixels alone does not make it a usable carousel.
Carry all destination uncertainty, including pair candidate ratio and simulated
gap, unchanged. No claims that sampled visual review proves platform crops.

</QA>

<Report>

edit-card; source and fresh bundle paths; fit, dimensions, any crop/padding/scale,
band and protected-region evidence; ordered tiles; measured versus visual QA;
`spend: free`; destructive-crop findings and unverified platform behavior.

</Report>
