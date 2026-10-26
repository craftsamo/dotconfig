# pixel

**Look.** A pixel-art sprite mascot on a coarse grid (about 64×64 logical
pixels for a full body), a small fixed palette (≤ 16 colours), 1 px dark
outline, no anti-aliasing, no gradients, hard-edged cluster shading.
The 16-bit era character-sprite family — a mascot that could stand in a
platformer's title screen.

**Prompt block.**
> pixel art sprite of <subject>, a mascot character design, 64x64 pixel
> grid, crisp hard-edged pixels, limited palette of <palette> (max 16
> colours), 1 pixel dark outline, no anti-aliasing, no gradients, no
> blur, 16-bit era sprite style, full body, standing, facing the viewer,
> centred, isolated on a plain flat <bg> background, no text, no
> watermark, no ground shadow

**Avoid.** Smooth shading, sub-pixel diagonals, the 'pixelated photo'
look, dithering noise as texture, more than 16 colours, a drawn ground
line under the feet.

**QA cues.** Zoom to 4×: pixels are square and aligned to one grid (no
half-pixel drift); palette count by eye ≤ 16; the cut-out edge is
stepped, not feathered; the finish resized by an integer factor (a
visible grid that drifted after the resize is a re-finish with a
different `--pad`, not a corrective).
