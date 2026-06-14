# Asset types — router

Identify the asset type first, then follow its **strategy** and reference. Sizes
are typical defaults; always prefer sizes discovered from the destination
(`discovery.md`).

| Asset type | Typical size / ratio | Strategy | Reference |
|---|---|---|---|
| In-app **cover** image | 16:9 master (e.g. 1792×1024); cropped to 2:1 / 21:9 | generate | `ai-imagery.md` |
| **Hero** / banner | 16:9 or 21:9, wide | generate | `ai-imagery.md` |
| **Illustration** / spot art | square or 16:9 | generate | `ai-imagery.md` |
| **OG image** | 1200×630 (1.91:1) | template + text | `text-cards.md` (+ `social-specs.md`) |
| **Twitter/X card** | 1200×630 (`summary_large_image`) | template + text | `text-cards.md` |
| **Social post** (IG/FB/LinkedIn) | 1080×1080 / 1080×1350 / 1080×1920 | generate (+ optional text) | `social-specs.md`, `ai-imagery.md` |
| **Favicon** | `.ico` 16/32/48 + `icon.svg` | derive-from-logo | `icons.md` |
| **apple-icon** | 180×180 PNG | derive-from-logo | `icons.md` |
| **PWA / Android icons** | 192, 512 + maskable (safe zone) | derive-from-logo | `icons.md` |
| **Slide / figure** | 16:9 (1920×1080) or 4:3 | generate or compose | `docs.md` |
| **Print figure** | physical size @ 300 DPI | generate or compose | `docs.md` |

## Strategy meanings

- **generate** — text-to-image via `image_generate`. Best for illustrative,
  non-text, brand-styled imagery. See `ai-imagery.md`.
- **derive-from-logo** — render the existing logo SVG to an exact icon set. AI
  generation cannot produce crisp tiny icons or exact-pixel sets — **do not use
  `image_generate`** here. See `icons.md`.
- **template + text** — a background (AI-generated or a solid brand fill) with the
  title/text **composited** on top (AI text is unreliable). See `text-cards.md`.

## Routing notes

- One destination can need several types (e.g. a web app has favicon + OG +
  in-app covers). Handle each by its own strategy; don't force one approach.
- OG/Twitter cards are "discovered in the codebase but sized by social specs" —
  use `discovery.md` to find them and `social-specs.md` for exact dimensions.
- When unsure of the type or size, ask the user before producing anything.
