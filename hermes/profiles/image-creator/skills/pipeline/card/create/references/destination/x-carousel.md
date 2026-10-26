---
width: 1080
height: 1350
square_width: 1080
square_height: 1080
tall_width: 1080
tall_height: 2160
tile_options: portrait|square|tall
display_width_css_px: 360
display_gap_css_px: 6
tiles: 3
max_tiles: 4
tile: portrait
status: user-observed-scroll
---

# X carousel

## Authoring defaults

Author 3 or 4 tiles: portrait 1080x1350 (4:5, default), square 1080x1080
(1:1), or tall 1080x2160 (1:2). Three tall tiles form a 3240x2160 panorama
(overall 3:2); four form 4320x2160. These are production choices, not verified
X limits or guaranteed crops. Four-tile behavior is not verified.

Render a full panorama and then exact adjacent crops; main title/brand/meta
belong to tile 1, independent tile_titles belong to their own tiles. Background
may cross seams; text must not. Never bake gaps into upload tiles or crop
seam content to compensate for UI spacing. Retain the original source-pixel
`gap` simulation; the separate display-scale simulation uses the metadata's
declared image width and effective image gap in CSS px (1 raster px per CSS px).
The display width is an authoring choice, not an observed viewport. Neither
preview is a platform screenshot. No test posts or authenticated access without consent.

## Browser observation recorded 2026-09-08

User-supplied Hermes Marketer browser evidence on the exact post:
https://x.com/timothymaarv/status/2096742510613708928

- Three still images, originals each 2048x4096 (1:2); loaded small images 340x680.
- Viewport 800x485, DPR 1: wrappers 336.516x673.047 CSS px; images
  334.516x671.047 CSS px.
- Emulated viewport 390x844, DPR 2: wrappers 158.078x316.156 CSS px;
  images 156.078x314.156 CSS px.
- Both views: wrapper gap 4 CSS px; effective image gap 6 CSS px from the
  1 CSS-px inset on each side. Horizontal scrolling and snap verified.
- Display ratio close to native, with no observed crop evidence. This is NOT
  a guarantee for all devices or a universal no-crop rule. Two-image behavior
  and a universal gap remain unverified; x-pair candidate is unchanged.

The display simulation borrows the observed effective gap, not X's wrappers,
viewport clipping, scroll/snap UI or device-pixel scaling.
