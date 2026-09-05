---
name: generate-mascot
description: >-
  A mascot character — a brand's, product's or team's — designed from a
  concept by an image model in a named style (game-2d, chibi,
  retro-cartoon, flat-vector, painterly, pixel, or a described one), in
  the client's palette, cut out on a transparent, chroma-key or flat
  background. Two rounds: without an `anchor` it draws three full-body
  concept candidates and stops for approval; with one it draws a pack on
  that character (turnaround, poses, or a custom list). The approved
  anchor is what every later asset of the character — an emoji pack, a
  sticker, a video — takes as its reference. Metered.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [mascot, generate, image_gen, character, style, metered]
    category: hands
    hands: image-creator
    cost: metered
    output: "round A: concept/concept_v<N>.png (full body, 1024 square, transparent) + sheet.png + silhouette.png; round B: pack/<slug>_<item>.png per item + sheet.png + manifest.json"
    form:
      concept:
        required: true
        type: text
        label: "who the mascot is — species or object, personality, the two or three features that make it recognisable, what it represents, where it will live"
        example: "開発ツール Forge のマスコット。小型の作業ロボット、好奇心旺盛で几帳面。頭にヘッドランプ、胸に六角ナットの紋章。README と Slack と動画に出る"
      style:
        required: true
        options: [game-2d, chibi, retro-cartoon, flat-vector, painterly, pixel]
        other: true
        label: "a listed style (references/styles/<style>.md), or a described look in a sentence"
      palette:
        required: false
        label: "the character's colours, as hex or words — two or three, in order of area"
        example: "electric blue + storm grey, a warm yellow accent"
      background:
        required: false
        options: [transparent, chromakey]
        other: true
        label: "transparent (default) | chromakey (the cut-out re-composited on flat #00ff00, for video keying) | #rrggbb flat fill"
      framing:
        required: false
        options: [full-body, bust, head]
        label: "how much of the character is drawn (default full-body; a mascot is designed whole and cropped later by edit-mascot)"
      reference:
        required: false
        type: image
        label: "a logo, sketch, existing character or brand image whose shape / motif / colours carry over (never copied)"
      anchor:
        required: false
        type: image
        label: "the approved concept from round A; present = draw the pack on it"
      pack:
        required: false
        options: [turnaround, poses, custom]
        other: true
        label: "round B: a listed pack (references/packs/<pack>.md), custom (items only), or a described set"
      items:
        required: false
        type: text
        label: "extra items, or the whole list for pack: custom — one per line, each `name: pose / expression / prop`"
        example: "wave: right hand raised in a wave, smiling\nthinking: hand on chin, eyes up"
      size:
        required: false
        type: int
        label: "canvas edge in px, square (default 1024)"
      slug:
        required: false
        label: "filename stem (default: a short slug of the character's name)"
      note:
        required: false
        type: text
---

<Procedure>

The two rounds exist because a mascot is the identity every later asset
copies: a pack — or an emoji set, or a video — drawn on the wrong
character is the most expensive mistake this leaf can make. Round A is
three images and stops.

0. Resolve the inputs. `size` defaults to 1024, `framing` to `full-body`,
   `background` to `transparent`. Load `references/styles/<style>.md` for
   a listed style; for a described one write an equivalent block yourself
   in the same shape (Look / Prompt block / Avoid / QA cues) into
   `<deliver>/style.md`. Write `<deliver>/character.md` — three lines
   that survive both rounds: the features that make the character
   recognisable (from `concept`, and from one vision look at `reference`
   when there is one: shape, motif, colours to carry over — never
   "copy"), the palette in order of area (from `palette`, else propose
   one from the reference or the concept and SAY so in the report), and
   what NOT to draw (incidental background, text, a second character).
   Choose `<bg>`, the flat colour the model draws on: pure white, unless
   the palette contains white or a pale colour, then `#00ff00`, unless
   the palette contains green, then `#0000ff`. The model cannot draw
   transparency; the finish cuts the subject out.

**Round A — the concept (no `anchor` in the form).**

1. Compose ONE prompt: "<style prompt block> of <character.md features>,
   <framing>, standing, facing the viewer, neutral friendly expression,
   feet visible (full-body), arms slightly away from the body" with
   `<palette>` and `<bg>` filled in. Arms away from the body matter: an
   arm against the torso makes an enclosed pocket the corner flood
   cannot reach. End with "single character, centred, no text, no
   watermark, no ground shadow". Write it to `<deliver>/concept/prompt.txt`
   BEFORE the first spend.
2. Generate 3 candidates (a `budget:` line `concept: N` overrides): one
   `image_generate(prompt, aspect_ratio="square",
   reference_image_urls=[<reference>])` per candidate — pass the
   reference only when there is one and the backend advertises the
   argument. Keep each raw file as `<deliver>/concept/raw/v<N>.<ext>`;
   append the model the tool reports to `prompt.txt`. A failed call is
   retried once, then counted.
3. Finish each candidate:

   ```
   ${HERMES_SKILL_DIR}/../../scripts/mascot-fit.sh <raw> <deliver>/concept/concept_v<N>.png \
     --size <size> --background <background> [--key "#0000ff"]
   ```

   Read `RESULT:`. `key_px` is the count of opaque pixels still near the
   removed background colour — background trapped in a pocket (between an
   arm and the body, under a tail, inside a handle) that the corner flood
   cannot reach at any fuzz. `key_px > 50` → re-run with `--cutout key
   --fuzz 30%`, which keys the colour everywhere and erodes 1 px; free.
   A cut-out that ate part of the character (coverage dropped, a limb
   missing on the sheet) is re-run with `--fuzz 5%`; a fringe of the
   background colour on the edge with `--fuzz 16%`, then `30%`. All of
   that is free and comes before any corrective generation. `pixel`:
   add `--pad 0.1` and confirm the grid survived the resize.
4. Look, in this order, writing the finding down after each look:
   (a) one contact sheet of the candidates —
   `magick <v1> <v2> <v3> -resize 320x320 -background '#888888' -gravity
   center -extent 336x336 +append <deliver>/concept/sheet.png` (not
   `montage`: ImageMagick 7 here has no default font) — one line per
   candidate against `character.md`: features present, palette kept,
   style cues met; (b) the silhouette sheet —
   `magick <v1> <v2> <v3> -alpha extract -negate -resize 160x160
   -background white -gravity center -extent 176x176 +append
   <deliver>/concept/silhouette.png` — a mascot must be recognisable as a
   black shape: name the candidate whose silhouette reads best and any
   whose silhouette is a blob; (c) the best candidate alone at native
   size.
5. Stop. Report the candidates, the silhouette verdicts and your
   recommendation. Do NOT draw a pack — the client approves a concept,
   and the next request comes back as `intent: revise <this dir>` with
   `anchor: <the approved file>`.

**Round B — the pack (`anchor` present).**

6. Read the previous `prompt.txt`, `character.md` and `style.md` from the
   `revise` dir; `anchor` must be one of its candidates or another file
   the client supplied — either way it is now the ONLY reference. For a
   listed `pack`, read `references/packs/<pack>.md` and append `items`;
   for `custom`, `items` IS the list (fewer than 2 items → `Q1:`); for a
   described pack, write 4-8 items yourself into `<deliver>/pack.md` in
   the same table shape. Every item is `name: pose / expression / prop`;
   a name is a slug because it becomes the file name. Write
   `<deliver>/pack/prompt.txt` with the base prompt: "<style prompt
   block> of the same character as the reference image —
   <character.md features> — <ITEM>, <framing unless the item names
   one>, <bg> background, single character, centred, no text, no
   watermark, no ground shadow". A prop that carries the item (a flag, a
   wrench, a speech bubble) is written LARGE, saturated and clear of the
   body's own colours — earned on the emoji family: pale or small props
   vanish at display size.
7. Generate one image per item, in the pack's order:
   `image_generate(<base prompt with ITEM filled>, aspect_ratio="square",
   reference_image_urls=[<anchor>])`. Keep raws as
   `<deliver>/pack/raw/<item>.<ext>`. Budget: 1 per item + ceil(n/4)
   correctives (a `budget:` line overrides). The calls run in the
   foreground one at a time; after every 4 items write the progress into
   `<deliver>/pack/progress.md` so a timeout loses nothing.
8. Finish every item with the same `mascot-fit.sh` options as the anchor
   (a character that needed `--cutout key` in round A needs it for every
   item). Write the calls into `<deliver>/pack/finish.sh` and run it with
   `bash`: an inline `for` loop over a script variable trips the terminal
   guard, a script file does not.
9. Look, in this order: (a) a contact sheet of the pack at 256 px on a
   grey ground (`-resize 256x256 -background '#888888' -gravity center
   -extent 272x272`, `+append` rows of 4, `-append` the rows; a pack over
   eight is read in halves — a run holds about eight looks) — identity:
   every item is the anchor's character (same features, same palette,
   same proportions); (b) the same sheet at 25 % (`-resize 25%`) — every
   pose still reads at thumbnail size; (c) single items only where (a)
   or (b) raised a doubt, one at a time, writing the finding down before
   the next look.
10. Correctives: an item that fails identity or pose gets ONE
    regeneration with the prompt adjusted by what failed (append the
    change to `prompt.txt`), within the corrective budget; then stop.
11. Package: `<deliver>/pack/manifest.json` — `[{"item": "wave", "file":
    "<slug>_wave.png", "bytes": N, "passed": true|false}]`. Items that
    failed are packaged and marked, never dropped silently.

`intent: revise` on round A (a new concept round after feedback): read
the previous `prompt.txt`, change only what the form or the note changed,
keep the same `<bg>` and finish options, and number the candidates on
from the previous round (`concept_v4` …) so nothing is overwritten.

</Procedure>

<QA>

Every check with its evidence:

- **Round A** — per candidate: `RESULT:` shows `width=height=<size>`,
  `corner_alpha=0` (transparent) or `=1` (chromakey / fill), coverage
  0.2-0.7 for full-body (a character, not a blob and not a sliver),
  `key_px` ≤ 50; vision against `character.md`: every recognisable
  feature present (name them), palette kept, style cues from the style
  file each named with a verdict; one character, no text, no watermark,
  no ground shadow, feet visible for full-body.
- **Silhouette** — vision on `silhouette.png`: the recommended candidate
  is identifiable as a black shape; a candidate whose silhouette is a
  blob is named as such.
- **Round B, per item** — `RESULT:` as above; the cut-out has no ghost
  rectangle, no holes, no fringe.
- **Identity** — vision on the 256 px sheet: every item is the anchor's
  character (features, palette, proportions); name any drift.
- **Pose** — vision on the 25 % sheet: each item reads as the pose its
  line names at thumbnail size.
- **Style** — the style file's QA cues, on the sheet.
- **Count** — the number of files equals the number of items; the
  manifest lists every one with `passed`.

A failed check is one free re-finish when fuzz, key or pad can fix it,
else one corrective generation within budget, else marked in the manifest
and named in the report — never a silent delivery.

</QA>

<Report>

`generate-mascot` + round (A or B) + style + background; which backend
received the reference (the client's image left the machine for it);
round A: the candidates with their `RESULT:` numbers, vision and
silhouette lines, the proposed palette if the form had none, the
recommended concept, and the exact `revise` line the client sends back;
round B: the sheet path, the manifest path, each QA check with evidence,
items marked failed and why; `spend: img <calls>/<budget>` (correctives
included); anything Creator must decide.

</Report>
