# pixel

**Look.** Hand-authored-looking game sprites on the content table's native
grid, at most 16 shared opaque colours, crisp one-pixel outlines, stepped
clusters and binary transparency. The native grid is not the 1024px model
canvas; finishing reduces to it and previews enlarge by integer factors.

**Prompt block.**
> Pixel-art game asset, <item>, <palette>, limited shared 16-colour
> palette, chunky deliberate pixel clusters, one logical pixel outline,
> <prop perspective or front-facing UI>, no antialiasing, no gradients,
> isolated on flat <key colour>, no text, no ground plane, no watermark.

**Avoid.** Pixelated photographs, subpixel highlights, independent palettes
per item, noisy dithering, smoothed scaling, isometric UI buttons.

**QA cues.** Native-size silhouette reads, clusters are purposeful, line
thickness is constant, final pixels lie on the same integer grid. Exact
palette and alpha checks support but cannot replace visual inspection.
