---
name: generate-reimagine
description: >-
  A client's photo — a person, a pet, an object, a scene — re-rendered by
  an image model in a named style (3d-character, comic-book, chibi,
  70s-street, 80s-anime, or a described one) with the SAME subject, pose
  and composition: the photo is the edit input, not a reference. One or
  several styles per request, two candidates each, delivered at the
  photo's own size next to a comparison sheet. Metered; the photo leaves
  the machine for the backend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [reimagine, generate, image_gen, photo, style, restyle, metered]
    category: hands
    hands: image-creator
    cost: metered
    output: "<slug>_<style>_v<N>.<format> per candidate at the photo's size (or `size`), sheet_<style>.png (photo + candidates), manifest.json, qa.md"
    form:
      photo:
        required: true
        type: image
        label: "the photo to re-render — png / jpg / webp / heic on disk; a person, a pet, an object, a place"
        example: "~/Downloads/IMG_4021.jpg"
      style:
        required: true
        options: [3d-character, comic-book, chibi, 70s-street, 80s-anime]
        other: true
        label: "one listed style (references/styles/<style>.md), several as a comma list, or a described look in a sentence"
        example: "comic-book, 80s-anime"
      keep:
        required: false
        options: [identity+pose+composition, identity]
        label: "identity+pose+composition (default): the same photo drawn in the style — subject, pose, framing, background elements all kept | identity: only the subject is kept; the style's own world may replace the scene, clothes and camera"
      background:
        required: false
        label: "keep (default: the photo's background, restyled) or a described replacement in a sentence"
        example: "a neon-lit Tokyo alley at night"
      aspect:
        required: false
        options: [keep, square, portrait, landscape]
        label: "keep (default): the photo's own aspect and pixel size | square / portrait / landscape: the model's canvas, then fitted to `size`"
      size:
        required: false
        label: "output pixels as WxH (default: the photo's own size, long edge capped at 2048)"
        example: "1600x1200"
      format:
        required: false
        options: [png, webp, jpg]
        label: "output format (default png)"
      slug:
        required: false
        label: "filename stem (default: the photo's stem)"
      note:
        required: false
        type: text
---

<Procedure>

The photo is the SUBJECT, not a mood board: it goes to the backend as
`image_url` (the edit input) and never as `reference_image_urls`. What
the style may change is the rendering; what it must not change is
written down once, before any spend, and every look is judged against
that note.

0. Resolve the inputs. Measure the photo: `magick identify -format '%w
   %h %m' <photo>` (an HEIC that `magick` cannot read is converted first
   with `sips -s format png <photo> --out <deliver>/source.png`; that
   file is then the photo). `aspect` defaults to `keep`: the model's
   canvas is `landscape` when w > h × 1.15, `portrait` when h > w × 1.15,
   else `square`; an explicit `aspect` overrides the canvas. `size`
   defaults to the photo's own WxH with the long edge capped at 2048
   (scale both edges); an explicit `aspect` without `size` makes it the
   canvas's nearest 4:3 / 1:1 / 3:4 at long edge 1600. `format` defaults
   to `png`, `slug` to the photo's stem (ASCII-slugged), `keep` to
   `identity+pose+composition`, `background` to `keep`. Split `style` on
   commas; each token is a listed style (load
   `references/styles/<style>.md`) or a described one — for a described
   style write an equivalent block in the same shape (Look / Prompt
   block / Avoid / QA cues) into `<deliver>/style_<slug-of-it>.md` and
   treat that as its file. Four styles or more → tell the report the
   run will read sheets in halves.
1. Look at the photo ONCE with vision and write `<deliver>/subject.md`
   before anything else — the identity lock, five short lines: (a) the
   subject, what it is and the two or three features that make it THIS
   one (a person: face shape, hair, glasses, facial hair, skin tone,
   what they wear and its colours; a pet: breed, markings, collar; an
   object or a place: the shapes and colours that name it); (b) the
   pose or arrangement (where the subject is, which way it faces, what
   the hands do, what is in front / behind); (c) the framing (close-up
   / bust / full / wide; the camera height; what touches the edges);
   (d) the background in one phrase (what it is, its light); (e) what
   must NOT appear (text, watermark, a second person, a changed
   expression). With `keep: identity` only lines (a) and (e) are the
   lock; (b)-(d) become "free". A `background:` sentence replaces (d).
2. Compose ONE prompt per style and write them all to
   `<deliver>/prompt.txt` BEFORE the first spend, each under a
   `## <style>` heading, in THIS order: the style file's **Medium**
   line first (it says what the picture IS and that the photograph's
   own texture must go — an edit model left to itself returns the
   photo with a filter: three of the first four candidates on the
   roses run did, and the corrective that opened with the medium line
   passed), then the Prompt block with `<subject>` filled from (a),
   then "keep the composition of the photo exactly: the same pose
   <(b)>, the same framing <(c)>, the background <(d)> in the same
   medium; keep the subject's identity and expression exactly; no
   text, no watermark, no added people or objects". Write (b)-(d) as
   one sentence each — the lock is a checklist for YOUR looks, the
   prompt carries its gist. With `keep: identity` replace the pose /
   framing / background clauses with "a new scene in the style's own
   world: <the style's Look>", keeping the identity clause. A
   `background:` sentence goes in place of (d) verbatim. End every
   prompt with the canvas spelled out — "a WIDE HORIZONTAL landscape
   image, wider than tall, do not rotate" (or tall / square): the
   `aspect_ratio` argument alone is not honoured reliably — gpt-image-2
   transposed a landscape call twice in a row on the roses run, and
   only that clause fixed it.
3. Generate, per style, 2 candidates (a `budget:` line `N per style`
   overrides): `image_generate(prompt=<that style's prompt>,
   image_url=<photo>, aspect_ratio=<canvas>)`, one call at a time in
   the foreground, styles in the form's order. Keep each raw file as
   `<deliver>/raw/<style>_v<N>.<ext>` and append the model the tool
   reports to `prompt.txt` under that style. The `image_url` argument
   must be in the tool's schema (the chain advertises it when a member
   can edit); if it is absent, stop and report `backend cannot edit
   images` — never fall back to `reference_image_urls`, which would
   return a redraw of a different subject. A call that fails is retried
   once, then counted; a member that refuses the photo (a safety
   refusal on a face) is reported as such with the member's name — the
   chain moves on to the next member on its own. Measure every raw as
   it lands (`magick identify -format '%w %h'`): a raw whose
   orientation is transposed against the canvas is NOT a candidate —
   it is never finished with `cover` (that would crop half the photo's
   composition away); mark it `passed: false, note: transposed` in
   the manifest, keep the raw, and the next call for that style
   restates the orientation clause in capitals. After every 4 calls
   write `<deliver>/progress.md` (styles done, candidates on disk) so a
   timeout loses nothing.
4. Finish every candidate to the delivery size:

   ```
   ${HERMES_SKILL_DIR}/../../scripts/img-postprocess.sh <raw> <deliver>/<slug>_<style>_v<N>.<format> \
     --size <WxH> --fit cover --format <format>
   ```

   Write the calls into `<deliver>/finish.sh` and run it with `bash`
   (an inline `for` loop trips the terminal guard, a script file does
   not). `cover` crops a canvas whose ratio differs from the photo's by
   a few percent; a crop that would remove more than 10 % of an edge
   (the model returned a different ratio) is a finding, not a silent
   trim — finish it with `--fit contain` instead and say so.
5. Look, and after EVERY look append the finding to `<deliver>/qa.md`
   before the next `vision_analyze` — APPEND (the patch tool, or a
   read-then-write that keeps the earlier text): a whole-file write
   replaced look 1 with look 2 on the roses run and it had to be
   restored from memory (an image is gone from the context three looks
   later; a run that looks without writing walks in a circle). Per
   style, in this order:
   (a) the comparison sheet — the photo first, then the candidates:
   `magick <photo> <v1> <v2> -resize 480x480 -background '#888888'
   -gravity center -extent 496x496 +append <deliver>/sheet_<style>.png`
   (not `montage`: no default font here) — write, per candidate, each
   line of `subject.md` with kept / drifted (name what drifted: a
   changed face, a mirrored pose, a cropped hand, a new object), then
   each of the style file's QA cues with a verdict, then "no text / no
   watermark / no added people";
   (b) the candidate you will recommend for that style, alone at
   delivery size — what the sheet could not show: the face or the
   subject's key detail up close, edge artefacts, a leftover photo
   texture where the style wants flat colour.
   That is two looks per style; four styles or more are read in
   halves, and a look the run could not reach is reported as a GAP,
   never guessed.
6. Correctives: a style whose BOTH candidates fail identity or the
   style cues gets ONE regeneration with the prompt adjusted by what
   failed (an identity drift → the drifted feature written explicitly
   and "do not change" in front of it; a style miss → the Medium line
   restated in capitals and the cue named from the Avoid list),
   appended to `prompt.txt`; each style has 1 corrective (a `budget:`
   line overrides) — styles fail independently, and the one shared
   corrective of the first run left the second style with a named
   defect and nothing to spend; then stop. A corrective is finished
   like the others and the sheet is REBUILT with every candidate
   (`photo | v1 | v2 | v3`), one more look (a) on it, appended — the
   earlier sheet look stays in `qa.md` as history.
7. Package `<deliver>/manifest.json` — `[{"style": "comic-book", "file":
   "<slug>_comic-book_v1.png", "bytes": N, "passed": true|false,
   "recommended": true|false}]`, one recommended per style that has a
   passing candidate; failed candidates are packaged and marked, never
   dropped silently.

`intent: revise <dir>`: read the previous `subject.md`, `prompt.txt`
and `manifest.json`; change only what the form or the note changed
(a new style = one more section, the same lock; a note about a drift =
the corrective wording); number candidates on from the previous round
(`_v3` …) so nothing is overwritten; the photo is looked at again only
when the note says the lock was wrong.

</Procedure>

<QA>

Every check with its evidence, per candidate:

- **Dimensions** — `img-postprocess.sh` printed `ok: … (<format>,
  <WxH>, …)` with the delivery `WxH`; the finish used `cover` with a
  crop under 10 % per edge, or `contain` was named in the report.
- **Identity** — vision on the sheet against `subject.md` (a): the
  subject is the same one — a person's face, hair, glasses and clothes;
  a pet's markings; an object's shapes — each named kept or drifted.
- **Pose and composition** — (`keep: identity+pose+composition`) vision
  on the sheet against (b) and (c): same pose, same facing, same
  framing, nothing mirrored, nothing cropped in; the background is (d)
  restyled, not replaced. (`keep: identity`) the scene is the style's
  own and the report says so.
- **Style** — the style file's QA cues on the sheet and the native
  look, each with a verdict; a candidate that still reads as the photo
  with a filter (photo texture, photographic noise, the original's
  lighting untouched where the style calls for flat cel light) is a
  style miss.
- **Clean** — no text, no watermark, no added people or objects, no
  border; the native look shows no edge artefacts or seams.
- **Count** — files on disk = styles × candidates (+ correctives);
  every one in the manifest with `passed` and exactly one
  `recommended` per style that has a pass.

A failed check is one corrective generation within budget, else marked
in the manifest and named in the report — never a silent delivery.

</QA>

<Report>

`generate-reimagine` + the styles + `keep`; **which backend member
received the photo** (the client's image left the machine for it — a
human client is told this before the handoff, Creator's job) and any
member that refused it; per style: the sheet path, the recommended
file, the second candidate, each QA check with its evidence from
`qa.md`, a `contain` finish or a crop over 10 % if one happened; the
manifest path; `spend: img <calls>/<budget>` (correctives included);
anything Creator must decide (a described style you had to write, a
style that failed twice and is out of correctives, the exact `revise`
line for one more style on the same lock).

</Report>
