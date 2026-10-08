# Techniques: OCR modes, contrast math, coordinate spaces, report shape

## Tesseract page-segmentation modes

`--psm N` changes how Tesseract decides what a "block of text" is. Running
several is cheap and each catches a different failure.

| PSM | Meaning | Use it for |
|---|---|---|
| 3 | Fully automatic, no OSD (default) | General baseline |
| 6 | Assume a single uniform block of text | Cards, banners, centered headings |
| 7 | Treat the image as a single text line | One-word / one-line artifacts |
| 8 | Treat the image as a single word | Logotypes, badges |
| 11 | **Sparse text — find as much as possible, no order** | **Stray watermarks, corner credits, scattered leftovers** |
| 12 | Sparse text with orientation & script detection | Same as 11, plus rotated text |
| 13 | Raw line, bypass Tesseract-specific hacks | Odd fonts PSM 7 mangles |

**PSM 11/12 are the ones that matter for absence claims.** PSM 6/7 assume a
single block and will happily ignore a small credit line in the corner — exactly
the thing you were asked to rule out. Always include 11 in the sweep.

Useful flags:
- `-l eng` — restrict language; reduces phantom glyph matches.
- `--oem 1` — LSTM engine only.
- `-c tessedit_char_whitelist=ABC...` — when you know the expected alphabet.
- Output goes to `stdout` when you pass `stdout` as the output base.

Install if missing: `brew install tesseract` (macOS) /
`apt-get install tesseract-ocr` (Debian).

## Apple Vision coordinate space

`VNRecognizedTextObservation.boundingBox` is **normalized 0..1 with the origin
at the BOTTOM-left** — not top-left like most image APIs. To convert to pixels
with a top-left origin:

```
px_x = box.origin.x * imageWidth
px_y = (1.0 - box.origin.y - box.height) * imageHeight
px_w = box.width  * imageWidth
px_h = box.height * imageHeight
```

Sanity check for a vertically centered single line: `box.origin.y + box.height/2`
should be ≈ `0.5`.

Set `usesLanguageCorrection = false` when verifying brand names, slugs, or
identifiers. With correction on, Vision can silently normalize a nonsense
string into a dictionary word and destroy the very evidence you are collecting.

`topCandidates(3)` is worth printing: a `conf=1.000` single candidate is a much
stronger claim than a top pick sitting among three near-ties.

## Contrast math (WCAG 2.x)

Relative luminance uses **gamma-corrected** channels — a plain
`0.2126R + 0.7152G + 0.0722B` on raw 0-255 values is wrong and will misreport:

```
c' = c/255;  lin = c'/12.92           if c' <= 0.03928
             ((c'+0.055)/1.055)^2.4   otherwise
L  = 0.2126*Rlin + 0.7152*Glin + 0.0722*Blin
ratio = (Lhi + 0.05) / (Llo + 0.05)
```

Thresholds: **4.5:1** AA normal text · **3:1** AA large text (>=18pt or >=14pt
bold) · **7:1** AAA.

**Core vs mean matters.** Averaging every non-background pixel folds in the
antialiased edge pixels and understates contrast substantially — one observed
case read 11:1 by mean but 18.9:1 using the modal glyph fill. Report the modal
(core) figure as the headline number; mention the mean only as a secondary.

## Proving absence

Ranked by strength:

1. **Pixel purity.** Zero pixels outside the text bbox differ from the
   background by even one unit -> nothing else is rendered. Deterministic and
   unarguable; no OCR needed. This is the result to aim for.
2. **Alpha check.** `getextrema()` on the alpha channel returning `(255,255)`
   rules out content hidden behind transparency.
3. **Boosted re-OCR.** Autocontrast plus a steep dark-range gain (`v*12`)
   exposes dark-on-dark text; re-run sparse-mode OCR on both variants.
4. **Two-engine agreement.** Tesseract and Apple Vision are unrelated
   implementations; agreement across both is meaningfully stronger than either
   alone.
5. **Explicit grep per variant**, with an `|| echo "none found"` fallback so a
   negative result is *visible* rather than being an empty, ambiguous output.

## Report shape

Lead with the verdict. Numbers in a table. Caveats last, honestly.

```markdown
## Verification Result: PASS

**Tool note:** <one line if you substituted instruments>

### 1. Visible text
`Dashboard` — one word, one line. Confirmed by:
- Apple Vision: 1 observation, conf 1.000
- Tesseract PSM 3/6/7/11/12: identical output

### 2. Colors (measured)
| | Value | Coverage |
|---|---|---|
| Background | `#09090b` | 98.67% |
| Text | `#fafafa` | 0.97% |

> Note: text is `#fafafa`, not pure `#ffffff`. Visually white; flagged because
> the spec said "white".

### 3. Centered and legible — yes
- bbox center (599.0, 314.5) vs image center (600.0, 315.0) -> off by 1.0px / 0.5px
- contrast 18.9:1 core — exceeds WCAG AAA (7:1)

### 4. No other text — confirmed
- Zero pixels outside the text bbox differ from background (max delta 0)
- Alpha fully opaque; boosted re-OCR still yields only `Dashboard`
- grep for `<forbidden>`: none found in any variant
```

Rules for the report:
- Every number traces to a command you actually ran.
- Discrepancies get surfaced as notes, never rounded into agreement.
- If you substituted instruments, say so in one line at the top — never imply
  you called a tool you did not call.
