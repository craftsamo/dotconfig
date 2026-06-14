# Text cards — OG / Twitter / title cards

A card = **background** + **title text composited on top**. Keep text out of the
generated image (AI text is unreliable); render it with a real font via
`scripts/text-card.sh` (ImageMagick + the brand font, e.g. Geist).

## When to use

- OG (`og:image`) and Twitter `summary_large_image` previews (1200×630) that show
  a title/branding.
- Any "title over art" card where the words must be crisp and correct.

## Background options

1. **AI-generated** brand art (`ai-imagery.md`) at `landscape`, cropped to
   1200×630 — keep a clear, lower-contrast zone where text will sit.
2. **Solid / gradient brand fill** (no generation) — fastest, most legible,
   perfectly on-brand. Often the better choice for OG.

## Procedure

1. Get the title text, brand color(s), and font (default Geist — installed via the
   Brewfile cask). Confirm 1200×630 (or the discovered size).
2. Prepare the background (option 1 or 2 above) at 1200×630 via
   `scripts/img-postprocess.sh`.
3. Composite the title:
   ```
   ${HERMES_SKILL_DIR}/scripts/text-card.sh <bg.png|--solid "#E26E54"> \
     --title "Course title" [--subtitle "..."] [--font Geist] \
     --color "#FFFFFF" --size 1200x630 --out og.png
   ```
   It wraps text, keeps a safe margin, and bottom/center-aligns per flags.
4. Review: title must be legible as a small unfurl thumbnail; keep within a ~10%
   safe margin (clients crop).

## Layout tips

- One short title + optional subtitle/logo. Avoid paragraphs.
- High contrast: light text on the brand fill, or a dark scrim over busy art.
- Place the logo (from `icons.md`/SVG) in a corner via compositing, not via AI.
- Keep a consistent template across pages for a cohesive set.

## Higher-fidelity option

For flexbox-style layouts and exact web typography, generate the card with
Satori-style HTML/CSS → SVG → PNG (`npx satori` / `@vercel/og`) instead of
ImageMagick. Use when the brand needs precise type/layout control.
