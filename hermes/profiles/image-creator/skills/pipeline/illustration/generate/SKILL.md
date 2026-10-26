---
name: generate-illustration
description: >-
  A text-free still drawn by an image model in a named or described look
  (a cover, hero, editorial or article illustration, thumbnail art, a
  background, document or social art), delivered as variants at an exact
  size and format next to a contact sheet. Exact words never go into the
  pixels. Metered: default 4 variants + 1 corrective.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [illustration, generate, image_gen, cover, hero, editorial, metered]
    category: hands
    hands: image-creator
    cost: metered
    output: "illustration_<slug>_v<N>.<format> per variant + sheet.png + prompt.txt + attempts.json + qa.md + one recommended variant"
    form:
      what_for:
        required: true
        label: "where the picture is used and for whom"
        example: "ブログ記事のヒーロー画像。エンジニア向けの技術解説"
      subject:
        required: true
        type: text
        label: "what the picture shows, as a scene or a motif; no words to be rendered in it"
        example: "a lighthouse on a cliff above a calm sea at dusk"
      style:
        required: true
        label: "a look in words: a named art style or a medium, free text"
        example: "soft watercolor with a muted teal palette"
      size:
        required: false
        label: "WIDTHxHEIGHT or an aspect like 16:9 (default 1536x1024)"
      format:
        required: false
        label: "png, webp or jpg (default png)"
      reference:
        required: false
        type: image
        label: "optional appearance reference; needs explicit upload consent and backend reference support before use"
      avoid:
        required: false
        type: text
        label: "what must not appear"
      variants:
        required: false
        type: int
        label: "variants to generate (default 4)"
      note:
        required: false
        type: text
---

<Procedure>

The picture carries no readable words: lettering is a card
(`create-card`, `generate-card`), not this leaf.

0. Budget. Read the handoff's `budget:` line; without one the allowance is
   `variants` (default 4) + 1 corrective, TOTAL across resumes, and it is
   not a larger grant than the user gave. Persist the cap and the grant in
   `<deliver>/attempts.json`. On every resume read it first and never reset
   spent calls. Record each call BEFORE making it; a failed or unknown
   call counts and is never a free retry. A larger cap needs a renewed
   grant. No grant for the planned count means a proposal or blocker with
   zero media calls.
1. Resolve the inputs. `size`: `WxH`, or an aspect → the nearest canvas of
   long edge 1536 (16:9 → 1536x864); default 1536x1024. Pick the model
   canvas from the ratio — `landscape` when w > h × 1.15, `portrait` when
   h > w × 1.15, else `square`. `format` defaults to `png`; the slug is a
   short ASCII slug of `subject`. With a `reference`, confirm upload
   consent first (a local path alone is not consent); with it, look at the
   image once (vision) and write two lines of what to carry over — shape,
   palette, mood — never "copy"; without consent, proceed from the text
   alone and say so. Craft: `references/craft-notes.md`.
2. Compose ONE prompt and write it to `<deliver>/prompt.txt` BEFORE the
   first spend: the medium and look from `style` first, then the subject,
   composition and palette, then the quiet areas the use needs, then
   "no text, no letters, no numbers, no logos, no watermark" plus `avoid`
   verbatim, then the canvas spelled out ("a WIDE HORIZONTAL landscape
   image, wider than tall, do not rotate", or tall / square). Never put a
   readable word, a letter, a number or a logo name in the prompt — a
   quoted string comes back as pixels. Append the model the tool reports
   after each call.
3. Generate: `image_generate(prompt, aspect_ratio=<canvas>)`, one call at
   a time in the foreground, up to the budget. With a consented
   `reference` and `reference_image_urls` in the tool's schema, pass it;
   if the schema lacks it, rely on the two written lines and say so. Keep
   each as `<deliver>/raw/v<N>.<ext>` and measure it
   (`magick identify -format '%w %h'`): a raw whose orientation is
   transposed against the canvas is not a variant — mark it and restate
   the orientation clause in capitals on the next call.
4. Normalize each variant with a script file (an inline `for` loop trips
   the terminal guard): write the calls into `<deliver>/finish.sh` and run
   it with `bash`:

   ```
   bash ${HERMES_SKILL_DIR}/../../scripts/img-postprocess.sh <raw> <deliver>/illustration_<slug>_v<N>.<format> \
     --size <WxH> --fit cover --format <format>
   ```

   A crop that would remove more than 10 % of an edge is a finding: finish
   with `--fit contain` and say so.
5. Look. After EVERY look append the finding to `<deliver>/qa.md` before
   the next `vision_analyze` — append, never overwrite. First the sheet:
   `magick <v1> <v2> … -resize 384x384 -background '#888888' -gravity center
   -extent 400x400 +append <deliver>/sheet.png` (not `montage`: no default
   font here), one line per variant for subject, look, text and `avoid`;
   then the recommended variant alone at delivery size for detail, edges
   and any lettering the sheet hid. A variant that renders text, letters,
   pseudo-writing or a watermark fails and is marked, not delivered as
   passed.
6. Corrective: if no variant passes and budget remains, ONE corrective
   with the prompt adjusted by what failed (stray text → the no-text
   clause restated in capitals; look miss → the medium line first and the
   cue named), written into `prompt.txt` and `attempts.json`; finish it,
   rebuild the sheet with every variant, one more look appended. Then
   stop and report, whatever the outcome.
7. `intent: revise <previous dir>`: read `prompt.txt`, `attempts.json` and
   `qa.md` first; a corrective against the chosen variant within the
   remaining budget changes only what the note changed; number variants on
   (`_v5` …) and never overwrite earlier files. No remaining budget means a
   blocker asking for a renewed grant.

</Procedure>

<QA>

Every check with its evidence, per delivered variant:

- **Count / size / format** — files on disk equal calls that returned an
  image; `img-postprocess.sh` printed `ok: … (<format>, <WxH>, …)` with
  the requested `WxH` and format.
- **No text** — vision at native size: no text, watermark, logo or garbled
  letters anywhere, including signs and book spines.
- **Subject and look** — vision: it shows `subject` in the `style`'s
  medium; the form's use (quiet areas, crop safety) is respected.
- **Avoid** — nothing named in `avoid` appears.
- **Spend** — the spend line equals the calls recorded in `attempts.json`.

A variant that fails a check is still delivered but named as failing.
Recommend exactly one.

</QA>

<Report>

`generate-illustration` + style; paths of the variants, `sheet.png`,
`prompt.txt`, `attempts.json`, `qa.md`; the recommended variant and why in
one line; each QA check with its evidence; whether a reference left the
machine; `spend: img <calls>/<budget>` (corrective included); anything the
Assistant must decide.

</Report>
