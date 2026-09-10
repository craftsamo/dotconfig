---
name: analyze-icon
description: >-
  Findings on an existing icon file or icon set — legibility at 16 / 32 px,
  contrast on light and dark, safe-zone extent, colour count, alpha and
  background state, and consistency against a sibling icon — each with a
  measurement or a vision verdict and the leaf that would fix it. Returns
  text only; writes no deliverable. Zero spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [icon, analyze, qa, legibility, contrast, free]
    category: hands
    hands: image-creator
    cost: free
    output: "a findings table in the reply (no file); `deliver:` may be omitted"
    form:
      source:
        required: true
        type: path
        label: "the icon file, or a directory holding an icon set (every png/svg/webp in it is measured)"
        example: "~/Workspaces/Projects/Acme/public/icons/"
      what_for:
        required: false
        options: [favicon, app-icon, maskable, ui-glyph, social-avatar]
        other: true
        label: "where it will be used — decides which checks are blocking"
      against:
        required: false
        type: image
        label: "a sibling icon or the mark it must stay consistent with"
      note:
        required: false
        type: text
---

<Procedure>

1. Resolve `source`: one file, or every `*.png|*.svg|*.webp|*.jpg|*.ico`
   directly inside a directory (no recursion; an `.ico` is measured on its
   first frame). More than eight files → measure all,
   but look (vision) only at the largest, the smallest and any that a
   measurement flags.
2. Measure each file:

   ```
   ${HERMES_SKILL_DIR}/scripts/icon-measure.sh <file> [--sheet /tmp/analyze-icon/<stem>.png] [--against <against>]
   ```

   `MEASURE:` gives size, channels, opaque, coverage, corner_alpha,
   mark_bbox, mark_extent, colors (≥ 1 % of the opaque area), dominant,
   contrast_white / contrast_black. Ask for `--sheet` on the files you will
   look at; it lays out 16×4, 32×2, 64, 128 on grey, 64 on white and on
   black, and the `against` icon at 128.
3. Look at each sheet once (vision), writing the finding per cell before
   the next sheet: does the 16 px cell still read as the subject; does the
   32 px cell keep its inner shapes separate; is the mark visible on both
   white and black; does it match `against` in shape, weight and colour.
4. Judge by `what_for` (default: judge everything, block nothing):
   - `favicon` — 16 px legibility and 32 px inner shapes are blocking;
     `colors` ≤ 4 on the largest file is expected.
   - `app-icon` — must be opaque (`opaque=True`, no transparent corners:
     the OS rounds); 64 px legibility blocking; contrast is informational.
   - `maskable` — `mark_extent` ≤ 0.80 blocking; opaque blocking.
   - `ui-glyph` — `contrast_white` ≥ 3.0 or `contrast_black` ≥ 3.0 for the
     dominant colour (whichever surface it sits on) blocking; 16 px blocking.
   - `social-avatar` — 64 px legibility blocking; `mark_extent` ≤ 0.85
     warned (circular crops).
   At 16-32 px the `colors` count inflates with anti-aliasing; read it on
   the largest file only.
5. Produce nothing else. The sheets stay under `/tmp/analyze-icon/` (the
   OS clears it; a multi-file `rm` trips the terminal guard, so do not).

</Procedure>

<QA>

A finding without a measurement or a named vision verdict is not a
finding. Every row of the table names: the check, the file, the evidence
(`MEASURE:` field or "vision: <what was seen>"), PASS / WARN / FAIL, and
for WARN / FAIL the fix — `edit-icon` (pad, recolour, background, cut-out,
resize), `create-icon` (re-derive from the SVG), `generate-icon`
corrective (redraw), or "simplify the mark" (Creator's / the client's
decision, not yours).

</QA>

<Report>

`analyze-icon` + `what_for`; the findings table (check · file · evidence ·
verdict · fix); one line of overall verdict ("ships as favicon" / "not as
maskable: extent 0.84 > 0.80"); `spend: free`; anything Creator must
decide.

</Report>
