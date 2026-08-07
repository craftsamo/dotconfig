# Pixel art — decision surface

Still pixel assets: sprites, avatars, icons, logo reductions,
scenes, limited-palette illustration. Animation → `pixel-video.md`;
ordinary raster art → `generated-image.md`.

Technic `creator-pixel-art` · QA `pixel-art` · deterministic
(a generated base image is a separate budgeted stage) · card:
`deterministic-render` for settled reductions.

## Fix before release

- Native grid `W × H` and the integer-scale destination preview.
  **Grid-size fork**: a thin logo, glyph, diagonal, or circular mark
  may not survive the requested grid — settle the fork BEFORE
  production, not at review.
- Palette: named/fixed palette or a color cap; transparency rule.
- Source stance: reduction of a supplied asset (what features are
  protected) vs deliberate native-grid redraw vs generated base
  (separate `generated-image` line) — visual reference vs reduction
  target is a decision.
- Tile/sprite-sheet and batch-consistency requirements.

## Defaults

- Anchor: one locked palette (named or sample-derived) for any
  batch — items never quantize adaptively per asset.
- Budget shape: zero generation for reduction/redraw; the master is
  the native PNG, the preview is integer nearest-neighbor only.
