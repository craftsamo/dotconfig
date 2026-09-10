---
name: create-emoji
description: >-
  Text emoji (承認 / LGTM / 助かる / 神) — one to three lines of bold text
  drawn deterministically with a Japanese-capable font, in a colour, on
  transparency or a rounded tile, finished for a platform (Slack,
  Discord, Telegram, LINE) as a set with a manifest. Zero spend; the same
  items file reproduces the same bytes.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [emoji, create, text, deterministic, free]
    category: hands
    hands: image-creator
    cost: free
    output: "<platform>/<name>.<ext> per item + sheet.png + manifest.json (+ <slug>_<platform>.zip when more than one item)"
    form:
      items:
        required: true
        type: text
        label: "the emoji to draw — one per line as `name: text`; `|` inside the text breaks a line (max 3)"
        example: "shounin: 承認\nlgtm: LGTM\ntasukaru: 助かる|ます"
      color:
        required: false
        label: "text colour, #rrggbb or a word (default #e4572e)"
      tile:
        required: false
        label: "tile colour behind the text, #rrggbb (default none = transparent)"
      fit:
        required: false
        options: [stretch, contain]
        label: "stretch (default): the classic 文字絵文字 look, glyphs stretched to fill; contain: glyph shapes kept"
      outline:
        required: false
        type: int
        label: "outline width in px around the glyphs (default 0; 6-8 makes light text sit on any theme)"
      outline_color:
        required: false
        label: "outline colour (default #ffffff)"
      platform:
        required: false
        options: [slack, discord, telegram, telegram-emoji, line, generic]
        label: "where it is uploaded (default slack); sizes and caps come from emoji-fit.sh"
      font:
        required: false
        type: file
        label: "a font file to use instead of Hiragino Sans W8"
      slug:
        required: false
        label: "stem for the zip (default: the first item's name)"
      note:
        required: false
        type: text
---

<Procedure>

1. Write the items file `<deliver>/items.tsv`: one line per item,
   `name<TAB>text`, the `|` kept as the line break. A `name` is a slug
   (`a-z 0-9 _ -`) — it becomes the file name and the `:code:`; turn a
   Japanese name into romaji (承認 → `shounin`). Text goes through this
   FILE, never an argv string: Japanese punctuation on the command line
   trips the terminal guard. A colour given as a word becomes its hex
   here (`red` → `#e4572e`-ish is a decision: pick one and say which).
2. Render:

   ```
   ${HERMES_SKILL_DIR}/scripts/text-emoji.sh <deliver>/items.tsv <deliver> \
     --platform <platform> [--color "#rrggbb"] [--tile "#rrggbb"] [--fit stretch|contain] \
     [--outline PX] [--outline-color "#rrggbb"] [--font PATH]
   ```

   It prints one `RESULT:` line per item (platform size, bytes,
   `within_cap`, coverage) and a `SHEET:` / `MANIFEST:` line. The whole
   set renders in seconds; rerun the same file to get the same bytes.
3. Look at `<deliver>/sheet.png` with vision (128 px per item, grey
   ground): every item shows the text asked for, whole, in the colour
   asked for; nothing clipped at the canvas edge. Then shrink the sheet
   to a quarter (`magick sheet.png -resize 25% sheet32.png`) and look
   once more: a one-line item still reads at 32 px; a three-line item
   is expected to read only at 128 px — say so in the report rather
   than fail it.
4. More than one item: `zip -j <deliver>/<slug>_<platform>.zip
   <deliver>/<platform>/*` for the upload.
5. `intent: revise <previous dir>` — copy its `items.tsv`, change only
   the lines or options the form changed, render the whole set again
   (it is free) so the manifest stays whole.

</Procedure>

<QA>

Every check with its evidence, per item:

- **Dimensions / cap** — `RESULT:` shows the platform size and
  `within_cap=yes`.
- **Transparency** — `corner_alpha=0`; tile: `coverage` ≈ 0.95;
  no tile: coverage between 0.1 and 0.9.
- **Text** — vision on the sheet: the characters are the ones in the
  items file (read them back), none clipped, none garbled (a font that
  lacks a glyph shows a box — switch `--font` and rerun).
- **Colour** — vision: the text (and tile) are the asked colours;
  light text without an outline on a transparent ground is reported as
  invisible on light themes.
- **Legibility** — the quarter-size sheet: one- and two-line items
  read; three-line items are named as 128-px-only.
- **Count** — files, `RESULT:` lines and manifest entries all equal the
  number of items.

A failed check is a rerun with the option that fixes it (free) or a
finding — never a silent delivery.

</QA>

<Report>

`create-emoji` + platform + fit; the items file path; every item's
`RESULT:` numbers; the sheet, manifest and zip paths; each QA check
with its evidence; `spend: free (0 credits)`; anything Creator must
decide (a colour word you resolved, a name you romanised).

</Report>
