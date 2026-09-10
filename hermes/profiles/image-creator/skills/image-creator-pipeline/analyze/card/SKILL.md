---
name: analyze-card
description: >-
  Measurement and bounded visual findings on a single CARD, an ordered tile
  set or a panorama against a destination. Checks size, exact-copy readability,
  hierarchy, contrast and seams separately from unverified platform crops.
  No new or corrected media, no generation, posting or authenticated browsing.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [card, analysis, typography, panorama, free]
    category: hands
    hands: image-creator
    cost: free
    output: "measurement JSON and written findings only; no corrected media"
    form:
      files:
        required: true
        type: text
        label: "JSON ordered array of absolute PNG/JPEG/WebP paths, 1..4; retain order, not a single image field"
        example: '["/absolute/tile-01.png", "/absolute/tile-02.png", "/absolute/tile-03.png"]'
      input_kind:
        required: true
        options: [single, tiles, panorama]
        label: "single image, ordered tiles, or one full panorama; never infer from filenames"
      destination:
        required: true
        label: "canonical create-card destination or explicit custom WxH"
      tiles:
        required: false
        type: int
        label: "pair=2; carousel=3|4; required when it differs from destination default"
      tile:
        required: false
        label: "carousel portrait 4:5 (default)|square 1:1|tall 1:2; pair candidate (unverified ratio)"
      gap:
        required: false
        type: int
        label: "legacy source-image-px simulation gap 0..128, default 16; carousel CSS-px width/gap reported separately, no preview rendered"
      expected_text:
        required: false
        type: text
        label: "exact copy and any tile assignment to compare visually; absent means text correctness unverified"
      note:
        required: false
        type: text
---

<Procedure>

1. Load `skill_view("create-card")` for the selected destination's caveats,
   then read its linked file-based execution contract. Decode
   files from JSON to an actual ordered array. Tiles requires exactly 2 for
   pair or 3/4 for carousel; panorama requires one full-width input. Input
   paths are not permission to fetch/upload/post or inspect an account.
2. Write a task-local analysis JSON with the form's fields. Run:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/card.py analyze <absolute-spec.json>
   ```

   Retain stdout measurements if deliver was supplied; do not pass --out or
   produce corrected media. Dimensions mismatching the target are findings,
   not a reason to resize. Record file byte hashes and order so later review
   identifies the actual inputs. No OCR or platform validation is hidden here.
3. Look once at each file natively and once at reduced display size (360px
   width per tile, thumbnail 168px). For a panorama look once at the whole
   image then at most one native and one reduced detail per expected tile.
   Local scratch crops/resizes are diagnostic evidence only, never replacement
   media. Record every verdict in task-local qa.md before the next look; at
   most 1+2N looks. Existing ordered tiles can be inspected in supplied order
   without demanding an image field or inventing a panorama input.
4. Report readable text versus expected_text, hierarchy, contrast, missing
   glyphs, clipping and seam-adjacent copy. Without expected text, transcription
   is an observation, not proof of correctness. Without current authorized
   platform evidence, crop/gap behavior stays UNVERIFIED. Suggest fixes in
   words, never render them or publish a test.

</Procedure>

<QA>

Separate MEASURED (file order, width/height, bytes, target-size match, hashes),
VISUAL (bounded looks with evidence and uncertainty), and UNVERIFIED (platform
crop/gap, unsupported context, absent expected text). Pair 7:8 is a candidate,
X article 5:2 is user-verified ratio only, all stated pixels are authoring
choices. A simulated preview is not platform evidence. Never claim byte-exact
identity against a lossy derivative or infer perfect reassembly without data.

</QA>

<Report>

analyze-card; ordered input paths/input_kind and destination; measurements and
visual findings separately; severity and suggested next action in words;
`spend: free`; unverified checks. Optional report/QA paths only, no new media.

</Report>
