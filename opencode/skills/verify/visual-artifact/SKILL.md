---
name: verify-visual-artifact
description: >-
  Use when asked to confirm that a rendered image is correct by measurement:
  OCR text, exact colors, centering, contrast, leftover branding, hidden text
  (OG 画像, ソーシャルカード, スクリーンショット検証, 文字が中央か, 背景色, 旧ブランド名が
  残っていないか, "is the text legible and centered", "is the background the right
  hex", "confirm it says exactly X", "verify this rendered PNG", next/og output,
  favicons, chart exports, badge images). Reports measured pixel values and dual
  OCR results (Tesseract and Apple Vision). Not for creating or editing images or
  judging aesthetics.
license: MIT
compatibility: Needs python3 with Pillow and tesseract; Apple Vision OCR needs macOS with swift.
---

# Visual Artifact Verification

Prove — with measurements, not impressions — what a rendered image actually
contains.

## When to Use

Use when asked to confirm a generated image is correct: OpenGraph social cards,
`next/og` output, screenshots, favicons, chart exports, badge images,
design-token renders.

Trigger phrases:
- "Is the text legible and centered?"
- "Is the background the right hex?"
- "Does it still contain leftover upstream branding / the old product name?"
- "Confirm it says exactly X and nothing else."
- "Verify this rendered PNG / check this screenshot."

Not for: creating or editing images, or judging aesthetic quality. This skill
measures objective properties only.

## Core principle

**Report measured values, never expected values.** The requester usually tells
you what it is *supposed* to look like. That is a hypothesis, not an
observation. Every claim in your report must trace to a number you actually
computed or a string an OCR engine actually returned. If a measurement
contradicts the spec — even trivially — surface it rather than rounding it
into agreement.

## Workflow

### 1. Confirm the file is what it claims to be

```bash
ls -la <path> && file <path>
```

Catches truncated renders, 0-byte files, and HTML error pages saved with a
`.png` extension. Note the real dimensions — a "1200x630" card that reports
`600 x 315` means a scale-factor bug upstream.

### 2. Run the pixel probe

```bash
python3 scripts/inspect_image.py <path>
# optional: --threshold 90 (fg detection sensitivity)  --outdir /tmp
```

Ships with this skill (`scripts/inspect_image.py`, relative to this skill's directory). Requires Pillow. It reports:

| Output | What it proves |
|---|---|
| Top colors + % coverage | Exact background/foreground hex, no eyeballing |
| Corner samples | Background is uniform, not a gradient or letterbox |
| Foreground bbox + centering offset | Centering, in pixels, vs. true image center |
| Contrast ratio (core **and** mean) | Legibility against WCAG thresholds |
| Row bands | How many separate lines/blocks of content exist |
| Column bands | Rough glyph count — sanity-checks the OCR result |
| Out-of-bbox purity | Whether *anything at all* exists outside the text block |
| Alpha extrema | Content hidden via transparency |

It also writes contrast-boosted variants (`*-boost.png`, `*-darkboost.png`) for
step 4.

### 3. OCR with two independent engines

Never trust a single OCR pass for an absence claim. Agreement between two
unrelated engines is what makes "there is no other text" defensible.

```bash
# Engine A — Tesseract, several page-segmentation modes
for psm in 3 6 7 11 12; do echo "-- PSM $psm --"; tesseract <path> stdout --psm $psm 2>/dev/null; done

# Engine B — Apple Vision (macOS, no install needed)
swift scripts/ocr_vision.swift <path>
```

PSM 11/12 are the sparse-text modes — they are the ones that surface stray
corner watermarks that PSM 6/7 skip entirely. Apple Vision additionally returns
an **observation count** and normalized bounding boxes, so "exactly 1 text
region" becomes a hard number.

See `references/techniques.md` for the PSM mode table and how to read Vision's
normalized coordinates.

### 4. Sweep for hidden / low-contrast text

An absence claim is only as good as your sensitivity. Two checks:

- **Out-of-bbox purity** (from step 2). If *zero* pixels outside the text
  bounding box differ from the background by even one value, nothing else is
  rendered — no OCR needed to prove it. This is the strongest possible result
  and short-circuits the rest.
- **Re-OCR the boosted variants.** If purity is non-zero, run Tesseract again
  on `*-boost.png` and `*-darkboost.png` (12x gain on the dark range). Catches
  dark-on-dark text that is invisible at normal gamma.

### 5. Grep explicitly for forbidden strings

Do not rely on reading the OCR output yourself. Grep it, case-insensitively,
across every render variant:

```bash
for f in orig boost darkboost; do
  tesseract /tmp/$f.png stdout --psm 11 2>/dev/null | grep -iE 'oldbrand|old-slug|author-handle' || echo "  none found"
done
```

An explicit `none found` line per variant is the evidence. A silent grep that
returns nothing is indistinguishable from a grep that failed to run.

### 6. Report a verdict first

Lead with **PASS** / **FAIL**. Then the measurements, ideally as a small table.
Then any caveat. Keep it tight — the requester wants the verdict and the
numbers, not your process narrative. Template in `references/techniques.md`.

## Pitfalls

- **Antialiasing drags the contrast ratio down.** Averaging every non-background
  pixel includes the grey edge pixels and can understate contrast badly (seen:
  11:1 by mean vs 18.9:1 core). Compute contrast from the *modal* foreground
  color — the actual glyph fill — and report the core figure as primary.
- **Near-white is not white.** Tailwind's `zinc-50` (`#fafafa`), `neutral-50`,
  and friends read as "white" visually but are not `#ffffff`. Report the exact
  hex and flag the discrepancy as a minor note rather than failing the check or
  silently calling it white.
- **A single OCR engine cannot prove absence.** It can only prove presence. Pair
  it with the pixel-purity check, which is deterministic.
- **Bounding-box center is not text center for descenders.** A word with a `y`
  or `g` extends the bbox downward, biasing vertical-centering math. Sub-pixel
  offsets (<2px) are noise; only flag meaningful drift.
- **Column band count != letter count.** Bold weights make adjacent glyphs
  touch and merge into one band. Use it as a sanity check, not an assertion.
- **Prefer a script file over inline `python3 -c`.** Writing the probe to a file
  keeps it reviewable and re-runnable, produces cleaner diffs in your report. The scripts here are already file-based for that reason.

## Files

- `scripts/inspect_image.py` — the pixel probe (Pillow); all measurements in one pass.
- `scripts/ocr_vision.swift` — Apple Vision OCR with confidence + bounding boxes (macOS).
- `references/techniques.md` — PSM modes, WCAG math, Vision coordinate space, report template.
