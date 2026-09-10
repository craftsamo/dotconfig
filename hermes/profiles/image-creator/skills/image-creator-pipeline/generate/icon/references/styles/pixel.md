# pixel

**Look.** Crisp 1-bit-edged pixel art on a coarse grid (16×16 to 32×32
logical pixels), a small fixed palette (≤ 8 colours), optional 1 px dark
outline, no anti-aliasing, no gradients. Retro game sprite family.

**Prompt block.**
> pixel art icon of <subject>, 24x24 pixel grid, crisp hard-edged pixels,
> limited palette of <palette> (max 8 colours), 1 pixel dark outline, no
> anti-aliasing, no gradients, no blur, centred, isolated on a plain flat
> <bg> background, no text, no watermark

**Avoid.** Smooth shading, sub-pixel diagonals, 'pixelated photo' look,
dithering noise as texture, more than 8 colours.

**QA cues.** Zoom to 4×: pixels are square and aligned to one grid (no
half-pixel drift); palette count by eye ≤ 8; the cut-out edge is stepped,
not feathered. A model output that is smooth is a corrective, not a pass.
