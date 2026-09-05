---
name: generate-emoji
description: >-
  A custom-emoji pack of one character — the client's face, pet or
  mascot from a reference photo, or a described one — drawn by an image
  model in a named style (chibi-cartoon, kawaii-pastel, pixel,
  flat-sticker, clay, or a described one) across a pack of expressions
  (expressions, gaming, love-hype, meme-classics, custom), finished for a
  platform (Slack, Discord, Telegram, LINE). Two rounds: without an
  `anchor` it draws the character sheet and stops for approval; with one
  it draws the pack on that anchor. Metered.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [emoji, generate, image_gen, character, pack, metered]
    category: hands
    hands: image-creator
    cost: metered
    output: "round A: anchor/anchor_v<N>.png (character sheet, 1024 square, transparent); round B: <platform>/<slug>_<item>.<ext> per item + sheet.png + manifest.json + <slug>_<platform>.zip"
    form:
      what_for:
        required: true
        label: "who the character is (name, species, defining features) and where the pack will be used"
        example: "うちの柴犬モチ。右耳が少し垂れている。チームの Slack 用"
      reference:
        required: false
        type: image
        label: "a photo of the face / pet / mascot to draw (identity comes from here); absent = drawn from what_for"
      pack:
        required: true
        options: [expressions, gaming, love-hype, meme-classics, custom]
        other: true
        label: "a listed pack (references/packs/<pack>.md), custom (items only), or a described theme"
      items:
        required: false
        type: text
        label: "extra items, or the whole list for pack: custom — one per line or comma-separated, each `name: expression / pose / prop`"
        example: "nemui: eyes half closed, yawning\nkami: sparkling eyes, hands raised"
      style:
        required: true
        options: [chibi-cartoon, kawaii-pastel, pixel, flat-sticker, clay]
        other: true
        label: "a listed style, or a described look in a sentence"
      platform:
        required: false
        options: [slack, discord, telegram, telegram-emoji, line, generic]
        label: "where it is uploaded (default slack); sizes and caps come from emoji-fit.sh"
      anchor:
        required: false
        type: image
        label: "the approved character sheet from round A; present = draw the pack on it"
      palette:
        required: false
        label: "colours to keep, as hex or words (fur colour, a signature accessory)"
      stroke:
        required: false
        type: int
        label: "outline px around each emoji (default 0; telegram default 12)"
      slug:
        required: false
        label: "filename stem (default: a short slug of the character's name)"
      note:
        required: false
        type: text
---

<Procedure>

The two rounds exist because a pack is 10-20 metered images of ONE
character: a wrong character discovered after the pack is the most
expensive mistake this leaf can make. Round A is cheap and stops.

0. Resolve the inputs. `platform` defaults to `slack`; `stroke` defaults
   to 12 for `telegram`, else 0. Load `references/styles/<style>.md` for
   a listed style; for a described one write an equivalent block yourself
   in the same shape (Look / Prompt block / Avoid / QA cues) into
   `<deliver>/style.md`. For a listed `pack`, read
   `references/packs/<pack>.md` and append `items`; for `custom`, `items`
   IS the list (fewer than 3 items → `Q1:`); for a described pack, write
   8-12 items yourself into `<deliver>/pack.md` in the same table shape.
   Every item is `name: expression / pose / prop` — a name is a slug
   (`lol`, `nemui`), because it becomes the file name and the `:emoji:`
   code. With a `reference`, look at it once (vision) and write three
   lines into `<deliver>/character.md`: the defining features to keep
   (ear shape, markings, glasses, hair), the colours, and what NOT to
   carry (background, clothing that is incidental). Without one, write
   the same three lines from `what_for`.

**Round A — the character sheet (no `anchor` in the form).**

1. Compose ONE prompt: "<style prompt block> of <character.md features>,
   front-facing head-and-shoulders, neutral friendly expression, looking
   at the viewer" with `<palette>` and `<bg>` filled in. `<bg>` is a
   flat colour that appears nowhere on the character — pure white, or
   `#00ff00` when the palette contains white — because the model cannot
   draw transparency; the finish cuts the subject out. End with "single
   character, centred, no text, no watermark". Write it to
   `<deliver>/anchor/prompt.txt` BEFORE the first spend.
2. Generate 3 candidates (budget line `anchor: N` overrides): one
   `image_generate(prompt, aspect_ratio="square",
   reference_image_urls=[<reference>])` per candidate — the reference is
   what carries identity; omit the argument only when there is no
   reference. Keep each raw file as `<deliver>/anchor/raw/v<N>.<ext>`;
   append the model the tool reports to `prompt.txt`. A failed call is
   retried once, then counted.
3. Finish each candidate for looking, not for upload:
   `${HERMES_SKILL_DIR}/../../scripts/emoji-fit.sh <raw> <deliver>/anchor/anchor_v<N> --platform generic`
   (512 PNG, transparent). A cut-out that ate part of the character or
   left a fringe is re-run with another `--fuzz` first (`5%` ate it;
   `16%` then `30%` for a fringe on soft styles) — free — before any
   corrective generation. Background colour TRAPPED in an enclosed
   pocket (between long side locks and the shoulders, under an arm) is
   not a fuzz problem — the corner flood cannot reach it at any value;
   re-run with `--cutout key --fuzz 30%`, which keys the colour
   everywhere and erodes 1 px (earned on a long-haired character: 68
   stray pixels became 2). Measure what is left rather than trusting the
   eye: `magick <png> -alpha off -fuzz 25% -fill white +opaque '#00ff00'
   -fill black -opaque '#00ff00' -negate -format '%[fx:mean*w*h]' info:`
   counts the key-coloured pixels.
4. Look: one contact sheet of the candidates (`magick <v1> <v2> <v3>
   -resize 256x256 -background '#888888' -gravity center -extent 272x272
   +append <deliver>/anchor/sheet.png` — not `montage`, ImageMagick 7
   here has no default font) with vision, writing one line per candidate
   against `character.md`: features kept, colours kept, style cues met.
   Then the best one alone at native size.
5. Stop. Report the candidates and your recommendation. Do NOT draw the
   pack — the client approves an anchor, and the next request comes back
   as `intent: revise <this dir>` with `anchor: <the approved file>`.

**Round B — the pack (`anchor` present).**

6. Read the previous `prompt.txt`, `character.md` and `style.md` /
   `pack.md` from the `revise` dir; `anchor` must be one of its
   candidates or another file the client supplied — either way it is now
   the ONLY reference. Write `<deliver>/pack/prompt.txt` with the base
   prompt: "<style prompt block> of the same character as the reference
   image — <character.md features> — <ITEM>, head-and-shoulders (or the
   pose the item names), <bg> background, single character, centred, no
   text, no watermark". Text belongs to `create-emoji`, never in pixels.
   A PROP that carries the expression (tears, a sweat drop, the "z", a
   hand at the chin) must be written as LARGE, saturated and clear of
   the hair and collar — earned on a live pack: pale tears and a small
   sweat drop vanished at 32 px and cost three correctives; "thick
   saturated blue tears past the chin" read at once. A hand placed on a
   white collar disappears; place it beside the cheek.
7. Generate one image per item, in the pack's order:
   `image_generate(<base prompt with ITEM filled>, aspect_ratio="square",
   reference_image_urls=[<anchor>])`. Keep raws as
   `<deliver>/pack/raw/<item>.<ext>`. Budget: 1 per item + ceil(n/4)
   correctives (a `budget:` line overrides). Long packs: the calls run
   in the foreground one at a time — after every 4 items write the
   progress into `<deliver>/pack/progress.md` so a timeout loses nothing.
8. Finish every item:
   `${HERMES_SKILL_DIR}/../../scripts/emoji-fit.sh <raw> <deliver>/<platform>/<slug>_<item> --platform <platform> [--stroke <stroke>]`
   — same fuzz and `--cutout key` rules as step 3 (a character that
   needed `key` in round A needs it for every item); the `RESULT:` line
   carries `within_cap`. `pixel`: add `--pad 0.02` and confirm the grid
   survived the resize. Write the twelve calls into
   `<deliver>/pack/finish.sh` and run it with `bash`: an inline `for`
   loop over a script variable trips the terminal guard, a script file
   does not.
9. Look, in this order: (a) a contact sheet of the whole pack at 128 px
   on a grey ground (`-resize 128x128 -background '#888888' -gravity
   center -extent 136x136`, `+append` rows of 6, `-append` the rows — a
   transparent sheet renders on a checkerboard and hides the edges) —
   identity across the set:
   every item is the same character as `anchor`; (b) the same sheet
   shrunk to 32 px per item (`-resize 25%`) and then point-magnified
   back (`-filter point -resize 400%` → `sheet32_zoom.png`) — vision
   cannot judge a 32 px tile, but the magnified one keeps exactly the
   32 px information; every expression still reads at the size it will
   be shown; (c) single items only where (a) or (b) raised a doubt, one
   at a time, writing the finding down before the next look. Vision
   holds about three images.
10. Correctives: an item that fails identity or expression gets ONE
    regeneration with the prompt adjusted by what failed (append the
    change to `prompt.txt`), within the corrective budget; then stop.
11. Package: `<deliver>/<platform>/manifest.json` — `[{"item": "lol",
    "code": ":<slug>_lol:", "file": "<slug>_lol.png", "bytes": N,
    "passed": true|false}]` — and `<deliver>/<slug>_<platform>.zip` of
    the platform directory (`zip -j`). Items that failed are packaged
    and marked, never dropped silently.

</Procedure>

<QA>

Every check with its evidence:

- **Round A** — per candidate: `RESULT:` shows `corner_alpha=0`,
  coverage 0.2-0.85; vision against `character.md`: features kept (name
  them), colours kept, style cues from the style file each named with a
  verdict; no text, no watermark, one character.
- **Round B, per item** — `RESULT:` shows the platform size,
  `within_cap=yes`, `corner_alpha=0`, coverage 0.15-0.9; the cut-out has
  no ghost rectangle, no holes, no fringe.
- **Identity** — vision on the 128 px sheet: every item is the anchor's
  character (same features, same colours); name any drift.
- **Expression** — vision on the 32 px sheet: each item reads as the
  expression its line names at that size; an expression that needs the
  128 px sheet to be read is a fail.
- **Style** — the style file's QA cues, on the 128 px sheet.
- **Count** — the number of files equals the number of items; the
  manifest lists every one with `passed`.

A failed check is one free re-finish when fuzz or pad can fix it, else
one corrective generation within budget, else marked in the manifest and
named in the report — never a silent delivery.

</QA>

<Report>

`generate-emoji` + round (A or B) + style + pack + platform; which
backend received the reference (the client's photo left the machine for
it); round A: the candidates with their `RESULT:` numbers and vision
lines, the recommended anchor, and the exact `revise` line the client
sends back; round B: the sheet path, the zip and manifest paths, each QA
check with evidence, items marked failed and why;
`spend: img <calls>/<budget>` (correctives included); anything Creator
must decide.

</Report>
