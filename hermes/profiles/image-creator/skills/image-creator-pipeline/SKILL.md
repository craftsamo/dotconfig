---
name: image-creator-pipeline
description: >-
  Root of image-creator's leaves. Load first, then the leaf a filled form
  names (`<verb>/<subject>`, verbs create | generate | edit | source |
  analyze). Holds the five-step run and the scripts several leaves share.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [image, hands, pipeline]
    category: hands
---

<Run>

The runtime specialist header is agent context outside the form, not human
approval. Preserve the initial must-keep conditions; do not weaken them to fit
a template. Use the leaf's supported authoring discretion. Distinguish a missing
input, environment failure and true capability gap before returning a finding.
Act only on the current agent request. The retained initial form supplies
historical constraints, never a request to repeat its generation or spend.

1. **Read the request as a form.** It names `skill:`, `intent:`, `deliver:`,
   optionally `budget:`, and `form:`. Load the leaf `skill_view("<skill>")`
   and compare `form:` against the leaf's front-matter `form`: every
   `required: true` field present and usable; a value outside `options` is
   accepted only when the field has `other: true`; `type: image|file|path`
   values must exist on disk. Missing or unusable → one batched `Q<n>:`
   block (2-4 options + recommendation), nothing produced. An unknown
   `skill:` → `no skill fits: <what was asked>`.
2. **Load what the leaf points at** — a `references/styles/<style>.md` for
   the chosen style, a listed reference image (vision), a previous delivery
   for `intent: revise`. Nothing else.
3. **Run `<Procedure>` exactly.** Scripts are invoked as the leaf writes
   them (`${HERMES_SKILL_DIR}/scripts/…`; shared ones live in this root's
   `scripts/`). Text with Japanese punctuation goes through a file, never
   an argv string. Anything that may exceed the terminal timeout runs
   `background: true` and is polled. A skill script runs in a command of
   its own: the write guard reads the WHOLE command, so `cp … && <skills
   path>/x.sh …` is refused as a write into the skill tree even though
   the script is only being run — copy first, run second, or put the
   calls into a script file under `deliver:` and `bash` it.
4. **Run `<QA>`**, every check with its evidence. Vision holds about three
   images: look at a contact sheet first, then single files one at a time,
   and after EVERY look append the finding as text to `<deliver>/qa.md`
   before the next `vision_analyze` — APPEND: the patch tool, or a
   read-then-write that keeps the earlier text; a whole-file write
   replaced look 1 with look 2 on the roses run. A look whose finding
   is not on disk did not happen — an image you looked at is gone from
   your context three looks later, and a run that looks without writing
   walks in a circle until the budget is spent (152 looks at three
   candidates on 2026-09-05). The leaf's `<Procedure>` lists the looks;
   that list is the budget, never "one more to be sure". A failed check
   is one free re-run when the leaf allows it, else a corrective within
   budget, else a reported gap — never a silent delivery.
5. **Reply with `<Report>`** — the paths, each check with evidence, the
   spend tally, and any one-line note about a procedure that no longer
   matches the runtime (reported, never patched: the tree is the
   maintainer's).

</Run>

<Shared scripts>

- `python3 scripts/card.py create|edit <absolute-spec.json> --out <new-absolute-bundle>`
  - deterministic card HTML/CSS/font rendering or explicit raster fit. Consumes
    create/card destination front matter and canonical style CSS blocks; isolated
    offline agent-browser, ImageMagick PNG crops, stable snapshots and exclusive
    output. Generate-card shares the composer, never duplicates its CSS.
- `python3 scripts/card.py analyze <absolute-spec.json>`
  - measured findings on declared single/ordered tiles/panorama inputs, no
    corrected media. See create/card/references/spec.md for file-based schemas.

- `scripts/img-postprocess.sh INPUT OUTPUT [--size WxH] [--fit cover|contain] [--format webp|png|jpg] [--max-bytes N]`
  — normalize any generated image (URL or path) to an exact size, format
  and byte cap; prints `ok: <path> (<format>, <WxH>, <bytes> bytes)`.
- `scripts/icon-finish.sh INPUT OUTPUT [--size PX] [--background transparent|tile|#rrggbb] [--tile #rrggbb] [--pad F] [--fuzz PCT] [--keep-bg]`
  — cut a subject out of a flat background (corner flood fill), fit it on
  a square canvas with the asked background; prints a `RESULT:` line.
- `scripts/emoji-fit.sh INPUT OUTPUT_STEM --platform slack|discord|telegram|telegram-emoji|line|generic [--cutout auto|yes|no] [--fuzz PCT] [--pad F] [--stroke PX] [--stroke-color #rrggbb]`
  — the emoji family's finish and the ONLY place the platform table lives
  (size, format, byte cap): cut-out unless the corners are already
  transparent, optional outline, fit, encode under the cap; prints a
  `RESULT:` line with `within_cap`.
- `scripts/mascot-fit.sh INPUT OUTPUT [--size PX] [--background transparent|chromakey|#rrggbb] [--key #rrggbb] [--cutout auto|yes|no|key] [--fuzz PCT] [--crop full|bust|head] [--crop-frac F] [--pad F] [--stroke PX] [--stroke-color #rrggbb]`
  — the mascot family's finish: cut a character out (corner flood or
  global key), optionally crop to the bust / head, fit on a square
  canvas on alpha, on a flat chroma key (re-composited, never the
  model's own green) or a flat fill; prints a `RESULT:` line with
  `key_px` (opaque pixels still near the removed background — a pocket
  the corner flood missed).
- `python3 scripts/kit-images.py fit INPUT OUTPUT --canvas WxH [--cutout auto|yes|no|key] [--fuzz N] [--pad F] [--pixel] [--palette PATH]`
  - rectangular contain-fit and cutout; pixel means native-grid nearest
  resampling, not proof of pixel authorship. Fit trims, so it is not a
  pivot-preserving transform of existing UI states.
- `python3 scripts/kit-images.py palette INPUT OUTPUT [--colors 16]`
  - shared foreground swatch strip, no transparent-background colours.
- `python3 scripts/kit-images.py atlas SOURCE OUTPUT_DIR [--columns 4] [--gap 2]`
  - full-frame grid atlas plus pixel coordinates, no trimming or extrusion.
- `python3 scripts/kit-images.py measure SOURCE --out OUTPUT_DIR [--against ANCHOR] [--palette PALETTE]`
  - measurements and bounded review sheets, no automatic visual verdict.
  Atlas/measure accept at most 64 PNGs per call; output directories must
  be empty and outside SOURCE. Split larger kits by category. These
  helpers are local-only; localize generated URLs before invoking them.

Leaves reach root scripts as `${HERMES_SKILL_DIR}/../../scripts/<name>`.

</Shared scripts>
