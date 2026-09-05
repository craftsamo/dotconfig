---
name: generate-icon
description: >-
  One icon drawn by an image model in a named style (flat-minimal, glass,
  pixel, line, clay, or a described one), cut out and delivered as square
  PNG variants at an exact size on a transparent, tiled or flat
  background. For a subject no icon library has, or a look no library
  draws. Metered: default 4 variants + 1 corrective.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [icon, generate, image_gen, style, metered]
    category: hands
    hands: image-creator
    cost: metered
    output: "icon_<slug>_v<N>_<size>.png per variant (square, default 1024) + prompt.txt + one recommended variant"
    form:
      what_for:
        required: true
        label: "what the icon depicts and where it will be used"
        example: "Slack 通知 bot のアプリアイコン。ベルと吹き出しを組み合わせたモチーフ"
      style:
        required: true
        options: [flat-minimal, glass, pixel, line, clay]
        other: true
        label: "a listed style, or a described look in a sentence"
      background:
        required: false
        options: [transparent, tile]
        other: true
        label: "transparent (default) | tile (subject on a rounded tile of tile_color) | #rrggbb flat fill"
      tile_color:
        required: false
        label: "tile colour for background: tile, #rrggbb (default #22d3ee)"
      palette:
        required: false
        label: "colours to use, as hex or words"
        example: "#2563eb, white, a warm accent"
      reference:
        required: false
        type: image
        label: "an image whose shape / motif / colours to carry over (not to copy)"
      size:
        required: false
        type: int
        label: "canvas edge in px, square (default 1024)"
      slug:
        required: false
        label: "filename stem (default: a short slug of what_for)"
      note:
        required: false
        type: text
---

<Procedure>

1. Load `references/styles/<style>.md` for a listed style; for a described
   style (`other`) write an equivalent prompt block yourself, one paragraph,
   in the same shape. With a `reference`, look at it once (vision) and write
   two lines of what to carry over: shape / motif / colours — never "copy".
2. Compose ONE prompt: the subject from `what_for`, the style's prompt
   block with `<subject>`, `<palette>` and `<bg>` filled in. `<bg>` is a
   flat colour that appears nowhere in the icon — pure white unless the
   palette contains white, then `#00ff00` — because the model cannot draw
   transparency; the finish cuts the subject out. Always end with "single
   object, centred, no text, no watermark". Write the prompt to
   `<deliver>/prompt.txt` BEFORE the first spend, and append the seed /
   model the tool reports after each call.
3. Generate the variants: one `image_generate(prompt, aspect_ratio="square")`
   call per variant, up to the budget (default 4). The tool returns a path
   or URL; keep each as `<deliver>/raw/v<N>.<ext>`. With a `reference` and a
   backend that advertises `reference_image_urls`, pass it; otherwise rely
   on the two written lines. A metered call that fails is retried once, then
   counted.
4. Finish every variant:

   ```
   ${HERMES_SKILL_DIR}/../../scripts/icon-finish.sh <raw> <deliver>/icon_<slug>_v<N>_<size>.png \
     --size <size> --background transparent|tile|"#rrggbb" [--tile "#rrggbb"] [--pad F]
   ```

   It flood-fills the flat background from the corners, trims, fits and
   prints one `RESULT:` line (measured size, bytes, coverage, corner_alpha).
   A cut-out that ate part of the subject or left a fringe is re-run with
   `--fuzz 5%` / `--fuzz 16%` first — that is free — before any corrective
   generation. For `pixel`, add `--pad 0.1` and never let the finish resize
   by a non-integer factor if the grid is visible (resize to a multiple).
5. Look: one contact sheet of all variants — `magick <v1> <v2> … -resize
   256x256 -background '#888888' -gravity center -extent 272x272 +append
   <deliver>/sheet.png` (not `montage`: ImageMagick 7 here has no default
   font and aborts) — with vision, writing a line per variant; then the best
   one alone at native size; then the same scaled to 64 px.
6. If no variant passes QA and budget remains, ONE corrective generation
   with the prompt adjusted by what failed (write the change into
   `prompt.txt`). Then stop and report, whatever the outcome.
7. `intent: revise <previous dir>` — read that `prompt.txt` first; change
   only what the form changed; keep the same `<bg>` and finish options.

</Procedure>

<QA>

Every check with its evidence, per delivered variant:

- **Dimensions** — `width=<size> height=<size>` in `RESULT:`.
- **Background** — `transparent`: `corner_alpha=0` and `coverage` between
  0.15 and 0.85; `tile`: `coverage` ≈ 0.95; `#rrggbb`: `coverage=1`.
- **Cut-out** — vision at native size on a contrasting background: no
  rectangular ghost of the generated background, no holes inside the
  subject, no fringe of the background colour on the edge.
- **Subject** — vision: it is what `what_for` describes, one object,
  centred, no text, no watermark.
- **Style** — the style file's "QA cues", each one named with its verdict.
- **64 px** — the icon still reads as its subject at 64 px.

Recommend exactly one variant. A variant that fails a check is still
delivered but named as failing; the report says why.

</QA>

<Report>

`generate-icon` + style + background; `prompt.txt` path; every variant's
path with its `RESULT:` numbers and the QA verdicts; the recommended
variant; `spend: img <calls>/<budget>` (corrective included); anything
Creator must decide.

</Report>
