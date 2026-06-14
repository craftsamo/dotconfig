# Social / sharing specs

Fixed dimensions for common platforms. Generate at the nearest `image_generate`
ratio (`landscape`/`portrait`/`square`), then crop/resize to the **exact** size
with `scripts/img-postprocess.sh`. For cards with a title, see `text-cards.md`.

## Sharing previews (Open Graph / cards)

| Use | Size (px) | Ratio | Notes |
|---|---|---|---|
| Open Graph (`og:image`) | 1200×630 | 1.91:1 | FB/LinkedIn/Slack/Discord unfurl |
| Twitter/X `summary_large_image` | 1200×630 | 1.91:1 | min 300×157, ≤ 5 MB |
| Twitter/X `summary` | 144×144+ | 1:1 | small square thumb |
| LinkedIn share | 1200×627 | ~1.91:1 | |

Keep critical content **centered** with ~10% safe margin — clients crop slightly
and show different ratios.

## Instagram

| Use | Size (px) | Ratio |
|---|---|---|
| Square post | 1080×1080 | 1:1 |
| Portrait post | 1080×1350 | 4:5 |
| Story / Reels | 1080×1920 | 9:16 |

## Facebook

| Use | Size (px) | Ratio |
|---|---|---|
| Shared link (OG) | 1200×630 | 1.91:1 |
| Feed image | 1200×1200 | 1:1 |
| Cover | 851×315 | ~2.7:1 |

## X / Twitter profile

| Use | Size (px) | Ratio |
|---|---|---|
| Header | 1500×500 | 3:1 |
| Profile photo | 400×400 | 1:1 |

## YouTube

| Use | Size (px) | Ratio |
|---|---|---|
| Thumbnail | 1280×720 | 16:9 | ≤ 2 MB |
| Channel banner | 2560×1440 | 16:9 | safe area 1546×423 center |

## Format & size

- Prefer **JPEG/WebP** for photos/rich art, **PNG** for flat/transparent.
- Respect per-platform max bytes; cap with `img-postprocess.sh --max-bytes`.
- These specs drift over time — if precision matters, confirm the current value.
