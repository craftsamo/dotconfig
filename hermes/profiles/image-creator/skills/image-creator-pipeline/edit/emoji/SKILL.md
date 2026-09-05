---
name: edit-emoji
description: >-
  Deterministic edits that turn an existing image or a delivered pack into
  platform-ready emoji: crop a face out of a photo and mask it to a circle
  or rounded square, cut a subject out of a flat background, add an
  outline, and re-finish for another platform (a Slack pack becomes a
  Telegram sticker set with a white stroke). Nothing is redrawn or
  generated. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [emoji, edit, crop, cutout, replatform, stroke, free]
    category: hands
    hands: image-creator
    cost: free
    output: "<platform>/<name>.<ext> per source image + sheet.png + manifest.json (+ <slug>_<platform>.zip when more than one)"
    form:
      source:
        required: true
        type: path
        label: "one image (png / webp / jpg / gif first frame), or a directory — a delivered <platform>/ dir re-platforms as a whole"
        example: "~/Workspaces/Projects/Acme/.agent/deliverables/emoji/slack/"
      platform:
        required: true
        options: [slack, discord, telegram, telegram-emoji, line, generic]
        label: "the platform to finish for; sizes and caps come from emoji-fit.sh"
      crop:
        required: false
        label: "a geometry WxH+X+Y applied first (the face out of a photo), or `square` for the centre square"
        example: "700x700+277+0"
      shape:
        required: false
        options: [circle, rounded]
        label: "mask the (cropped) image to a circle or a rounded square — the photo-emoji look, no cut-out needed"
      cutout:
        required: false
        options: [auto, "yes", "no", key]
        label: "remove a flat background: auto (default: only if the corners are opaque) | yes | no | key (global key for enclosed pockets)"
      stroke:
        required: false
        type: int
        label: "outline px around the subject (default 0; 12 is the Telegram sticker convention)"
      stroke_color:
        required: false
        label: "outline colour (default #ffffff)"
      slug:
        required: false
        label: "rename outputs `<slug>_<item>` (default: keep the source names)"
      note:
        required: false
        type: text
---

<Procedure>

1. At least one of `crop`, `shape`, `cutout: yes|key`, `stroke`, or a
   `platform` that differs from the source's must be present, or there is
   nothing to edit — `Q1:` asking which. Measure a single source first:
   `magick identify -format '%w %h %[channels] %[opaque]'`. A photo
   (opaque, non-flat background) cannot be cut out by flood fill — with
   no `shape` given, `Q1:` recommending `shape: circle` (or `rounded`);
   removing a real background is not this leaf. A `crop` you must choose
   yourself (the client said "my face" and gave a photo): look once with
   vision, pick a square around the head with the chin at ~85 % of the
   edge, and say the geometry in the report as a decision.
2. Run:

   ```
   ${HERMES_SKILL_DIR}/scripts/emoji-edit.sh <source> <deliver> --platform <platform> \
     [--crop WxH+X+Y|square] [--shape circle|rounded] [--cutout auto|yes|no|key] [--fuzz PCT] \
     [--stroke PX] [--stroke-color "#rrggbb"] [--slug <slug>]
   ```

   One `RESULT:` line per file (platform size, bytes, `within_cap`,
   coverage, corner_alpha) plus `SHEET:` / `MANIFEST:`. A cut-out that ate
   part of the subject or left a fringe is re-run with another `--fuzz`
   (`5%` ate it; `16%`, `30%` for a fringe); background colour trapped in
   an enclosed pocket needs `--cutout key` — all free.
3. Look at `<deliver>/sheet.png` with vision (128 px per item on grey):
   the crop holds the whole face, the mask edge is clean, the stroke is
   continuous, nothing important sits outside the circle. More than one
   file: also shrink the sheet to a quarter and point-magnify it back
   (`-resize 25% -filter point -resize 400%`) to judge the 32 px read.
4. More than one file: `zip -j <deliver>/<stem>_<platform>.zip
   <deliver>/<platform>/*` where `<stem>` is `slug`, else the prefix the
   item names share (`lethe_wink`, `lethe_cry` → `lethe`), else the
   source directory's parent name — never a platform name.
5. `intent: revise` — rerun with the changed option; same input + options
   reproduce the same bytes.

</Procedure>

<QA>

Every check with its evidence, per output:

- **Dimensions / cap** — `RESULT:` shows the platform size and
  `within_cap=yes`.
- **Transparency** — `corner_alpha=0`; `shape: circle` gives coverage ≈
  0.72 (π/4 of the padded square), `rounded` ≈ 0.95, a cut-out 0.15-0.9.
- **Crop / mask** — vision: the face is whole and centred, the mask edge
  is clean, no background colour survives inside a cut-out (count it:
  `magick <png> -alpha off -fuzz 25% -fill white +opaque '<bg>' -fill black
  -opaque '<bg>' -negate -format '%[fx:mean*w*h]' info:`).
- **Stroke** — vision: continuous around the silhouette, the asked colour.
- **Count** — files, `RESULT:` lines and manifest entries all equal the
  number of sources; a re-platformed pack keeps every item name.
- **32 px** (packs) — the point-magnified quarter sheet still reads.

A failed check is a rerun with the option that fixes it (free) or a
finding — never a silent delivery.

</QA>

<Report>

`edit-emoji` + platform + the edits applied; every output path with its
`RESULT:` numbers; the sheet / manifest / zip paths; each QA check with
evidence; `spend: free (0 credits)`; anything Creator must decide (a crop
you chose, a photo that needs real background removal).

</Report>
