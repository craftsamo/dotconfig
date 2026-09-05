---
name: edit-mascot
description: >-
  Deterministic edits on an existing mascot file or a delivered pack: swap
  the background (transparent, chroma-key for video, a flat fill), re-cut
  a subject out of a flat background (corner flood or global key), crop
  to the bust or the head for an avatar, resize, add an outline. Nothing
  is redrawn, recoloured or generated — a shaded character cannot be
  recoloured deterministically; that is a `generate-mascot` revise. Zero
  spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [mascot, edit, background, chromakey, crop, avatar, cutout, free]
    category: hands
    hands: image-creator
    cost: free
    output: "<name>.png per source image at the asked size / background / crop + sheet.png (+ <slug>.zip when more than one)"
    form:
      source:
        required: true
        type: path
        label: "one mascot image (png / webp / jpg), or a directory — a delivered concept/ or pack/ dir is edited as a whole"
        example: "~/Workspaces/Projects/Forge/.agent/deliverables/mascot/pack/"
      background:
        required: false
        options: [transparent, chromakey]
        other: true
        label: "transparent | chromakey (re-composited on flat #00ff00, or key_color) | #rrggbb flat fill"
      key_color:
        required: false
        label: "the chroma-key colour for background: chromakey (default #00ff00; #0000ff when the character has green)"
      crop:
        required: false
        options: [full, bust, head]
        label: "keep the whole character (default), or the top part for an avatar — bust ≈ top 55 %, head ≈ top 40 % of the subject's height"
      crop_frac:
        required: false
        label: "override the crop fraction, 0-1 from the top (a chibi head is taller: 0.5)"
      size:
        required: false
        type: int
        label: "canvas edge in px, square (default: keep the source's edge, or 1024 for a non-square source)"
      cutout:
        required: false
        options: [auto, "yes", "no", key]
        label: "remove a flat background: auto (default: only if the corners are opaque) | yes | no | key (global key for enclosed pockets)"
      fuzz:
        required: false
        label: "cut-out tolerance (default 10%; 5% when it ate the subject, 16-30% for a fringe)"
      stroke:
        required: false
        type: int
        label: "outline px around the subject (default 0)"
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

1. At least one of `background`, `crop`, `size`, `cutout: yes|key`,
   `stroke` must be present, or there is nothing to edit — `Q1:` asking
   which. Measure a single source first: `magick identify -format '%w %h
   %[channels] %[opaque]'`. A photo or a rendered scene (opaque,
   non-flat background) cannot be cut out by flood fill — that is not
   this leaf; say so. `size` defaults to the source's edge when it is
   square, else 1024.
2. One file — run:

   ```
   ${HERMES_SKILL_DIR}/../../scripts/mascot-fit.sh <source> <deliver>/<name>.png \
     --size <size> [--background transparent|chromakey|"#rrggbb"] [--key "#rrggbb"] \
     [--crop full|bust|head] [--crop-frac F] [--cutout auto|yes|no|key] [--fuzz PCT] \
     [--stroke PX] [--stroke-color "#rrggbb"]
   ```

   A directory — write one such line per image file (png / webp / jpg,
   sorted) into `<deliver>/edit.sh` and run it with `bash`: an inline
   `for` loop over a script variable trips the terminal guard, a script
   file does not. Each call prints one `RESULT:` line (size, bytes,
   coverage, `corner_alpha`, `key_px`, the options used).
3. Read every `RESULT:`. `key_px > 50` after a corner cut-out is
   background trapped in a pocket → re-run with `--cutout key --fuzz
   30%`. A cut-out that ate part of the character (coverage dropped) →
   `--fuzz 5%`; a fringe → `16%`, then `30%`. All free. A `head` crop
   whose subject is a chibi or a big-headed style comes out with the
   chin cut → `--crop-frac 0.5`.
4. Look at one sheet with vision — `magick <outputs…> -resize 256x256
   -background '#888888' -gravity center -extent 272x272 +append
   <deliver>/sheet.png` (rows of 4 with `-append` for more; not
   `montage`) — a chroma-key delivery is judged on the sheet as is (the
   green IS the deliverable): the subject is whole, the edge is clean
   with no fringe or halo, a crop holds the whole head with the chin
   inside, the stroke is continuous.
5. More than one file: `zip -j <deliver>/<stem>.zip <deliver>/*.png`
   where `<stem>` is `slug`, else the prefix the names share, else the
   source directory's parent name.
6. `intent: revise` — rerun with the changed option; same input + options
   reproduce the same bytes.

</Procedure>

<QA>

Every check with its evidence, per output:

- **Dimensions** — `RESULT:` shows `width=height=<size>`.
- **Background** — `transparent`: `corner_alpha=0`; `chromakey` /
  `#rrggbb`: `corner_alpha=1` and `channels` without alpha; the
  `background=` field names what was asked.
- **Cut-out** — `key_px` ≤ 50; vision: no ghost rectangle, no holes, no
  fringe of the old background on the edge.
- **Crop** — vision: `bust` / `head` hold the whole head with the chin
  inside the canvas; coverage 0.3-0.8.
- **Stroke** — vision: continuous around the silhouette, the asked colour.
- **Count** — output files and `RESULT:` lines equal the number of
  sources; a pack keeps every item name.

A failed check is a rerun with the option that fixes it (free) or a
finding — never a silent delivery.

</QA>

<Report>

`edit-mascot` + the edits applied; every output path with its `RESULT:`
numbers; the sheet / zip paths; each QA check with evidence; `spend:
free (0 credits)`; anything Creator must decide (a crop fraction you
chose, a source that needs real background removal or a redraw).

</Report>
