# Docs — slides, figures, print

Images for slide decks, documents, and print. Mostly `generate` (illustrations,
backgrounds) or `template + text` (title slides); icons still come from
`icons.md`.

## Slides

| Target | Size (px) | Ratio |
|---|---|---|
| Widescreen (Keynote/Google Slides/PPT) | 1920×1080 | 16:9 |
| Standard | 1024×768 | 4:3 |
| Full-bleed background | match slide size | 16:9 / 4:3 |

- Generate full-bleed art at `landscape`; crop to the exact slide size.
- Leave a calm area for slide text, or supply the title via `text-cards.md`.
- Inset figures: generate `square`/`landscape`, export PNG (transparent if it sits
  on a colored slide).

## Documents / figures

- Diagrams and spot illustrations: `square` or `landscape`, export **PNG**
  (transparent background when placed on a page) or **SVG** if vector is needed
  (AI raster can't produce true SVG — for crisp line vectors prefer the logo/icon
  pipeline or author the SVG).
- Keep a consistent style across a document's figures (locked style block).

## Print

- Work at **300 DPI**: pixels = inches × 300 (e.g. 4×6 in → 1200×1800 px). Note
  `image_generate` resolution is limited — generate the largest available, then
  upscale/sharpen in `img-postprocess.sh` only as needed; avoid tiny sources for
  large prints.
- Use **CMYK-safe** colors when the printer requires it (convert at export;
  expect some shift from screen RGB).
- Embed fonts / outline text in the final document; don't bake unreliable AI text
  into figures.

## Format

- Slides/screen: PNG (flat/transparent) or JPEG/WebP (photographic).
- Print: high-res PNG/TIFF; confirm the printer's required format/DPI/color space.
