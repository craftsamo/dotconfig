# isometric

**Look.** Game assets drawn in true isometric projection: 30-degree grid,
no perspective, a light top face and two darker side faces per material,
flat fills with an optional thin darker edge, a soft ambient base shadow
kept inside the silhouette. Tile-able world props for city builders and
management sims; UI stays front-facing and flat.

**Prompt block.**
> Isometric 2D game asset of <item>, <palette>, true 30-degree isometric
> projection with no perspective, light top face and two darker side
> faces, flat fills, thin darker edge, compact readable form, <prop
> perspective or front-facing UI>, isolated on flat <key colour>, no
> floor tile, no lettering, no watermark, no floor shadow.

**Avoid.** Perspective convergence, a floor tile or diorama base unless
the item is a tile, mixed angles between props, isometric UI chrome
(buttons and panels stay front-facing), thin details that break at 1x.

**QA cues.** Every prop shares the same projection angle and footprint
logic; face shading keeps one light direction across the kit; props
could sit on the same grid; UI items are flat and front-facing.
