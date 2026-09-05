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
   `background: true` and is polled.
4. **Run `<QA>`**, every check with its evidence. Vision holds about three
   images: look at a contact sheet first, then single files one at a time,
   and write each finding down before the next look. A failed check is one
   free re-run when the leaf allows it, else a corrective within budget,
   else a reported gap — never a silent delivery.
5. **Reply with `<Report>`** — the paths, each check with evidence, the
   spend tally, and any one-line note about a procedure that no longer
   matches the runtime (reported, never patched: the tree is the
   maintainer's).

</Run>

<Shared scripts>

- `scripts/img-postprocess.sh INPUT OUTPUT [--size WxH] [--fit cover|contain] [--format webp|png|jpg] [--max-bytes N]`
  — normalize any generated image (URL or path) to an exact size, format
  and byte cap; prints `ok: <path> (<format>, <WxH>, <bytes> bytes)`.
- `scripts/icon-finish.sh INPUT OUTPUT [--size PX] [--background transparent|tile|#rrggbb] [--tile #rrggbb] [--pad F] [--fuzz PCT] [--keep-bg]`
  — cut a subject out of a flat background (corner flood fill), fit it on
  a square canvas with the asked background; prints a `RESULT:` line.
  Leaves reach root scripts as `${HERMES_SKILL_DIR}/../../scripts/<name>`.

</Shared scripts>
