# pixel

**Look.** Crisp pixel art on a coarse grid (32×32 logical pixels), a
small fixed palette (≤ 12 colours), 1 px dark outline, no anti-aliasing,
no gradients. The retro-game portrait family — an emoji that looks like
a character-select sprite.

**Prompt block.**
> pixel art emoji of <subject>, 32x32 pixel grid, crisp hard-edged
> pixels, limited palette of <palette> (max 12 colours), 1 pixel dark
> outline, no anti-aliasing, no gradients, no blur, exaggerated
> expression, head-and-shoulders, centred, isolated on a plain flat <bg>
> background, no text, no watermark

**Avoid.** Smooth shading, sub-pixel diagonals, 'pixelated photo' look,
dithering noise as texture, more than 12 colours.

**QA cues.** Zoom to 4×: pixels are square and aligned to one grid (no
half-pixel drift); palette count by eye ≤ 12; the cut-out edge is
stepped, not feathered; the finish resized by an integer factor (a
visible grid that drifted after the resize is a re-finish with a
different `--pad`, not a corrective).
