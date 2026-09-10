# painterly

**Look.** A painterly character illustration: visible brush strokes,
soft edges where forms meet, rich lighting with a warm key and a cool
fill, textured colour instead of flat fills, no hard outline — the shape
is held by value contrast. Still a mascot: simplified appealing
proportions, a clear expression, one strong silhouette. The concept-art /
Ghibli-still / storybook family.

**Prompt block.**
> painterly character illustration of <subject>, a mascot design with
> simplified appealing proportions, visible brush strokes, soft edges,
> warm key light and cool fill light, rich textured <palette> colours, no
> hard outline, one strong clear silhouette, full body, standing, facing
> the viewer, centred, isolated on a plain flat <bg> background, no text,
> no watermark, no ground shadow, no environment

**Avoid.** A painted background or environment (it defeats the cut-out —
ask for the plain flat <bg> twice if the model keeps adding one),
photoreal rendering, muddy low-contrast values, a scene with more than
one figure, atmospheric haze at the edges (it becomes a halo after
cut-out).

**QA cues.** After cut-out the edge is clean — no halo of background
colour (a soft-edged style needs `--fuzz 16%` then `30%`; confirm with
vision that no limb was eaten); the silhouette still reads as a black
shape; the face has a clear expression at 256 px; the values separate
the character from any background (light on dark or dark on light).
