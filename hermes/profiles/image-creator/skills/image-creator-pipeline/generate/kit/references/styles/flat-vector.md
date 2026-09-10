# flat-vector

**Look.** Flat-colour geometric game assets with restrained outlines, no
texture or gradients. This generated route delivers raster PNGs, not
actual vectors; `create-kit` supplies SVG for deterministic UI geometry.

**Prompt block.**
> Flat vector-style game illustration, <item>, <palette>, simple geometric
> silhouette, consistent rounded corners and outline thickness, front
> facing UI or <prop perspective>, isolated on flat <key colour>, no
> texture, no gradient, no shadow, no text, no watermark.

**Avoid.** Pretending the generated PNG is an SVG, false 9-slice precision,
extra decorative strokes, bevels or brush texture.

**QA cues.** Clean silhouette, few colour roles, readable at use size. State
pairs have the same geometry; use create-kit if generative drift persists.
