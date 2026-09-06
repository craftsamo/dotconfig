# flat-vector

**Look.** Clean rounded-rectangle widgets on a real vector canvas: one flat
fill colour per shape, a thin flat-colour stroke, no gradients, no drop
shadows, no bevels. A button is a rounded rect; a window panel is a rounded
rect with a flat title-bar strip; a bar is a rounded outline (the frame)
plus a rounded fill inset inside it by the frame's own stroke width. The
"clean mobile-game HUD" family — Kenney/Godot-default rather than a AAA
diegetic HUD.

**Drawing rules.** Every shape is an SVG `<rect rx ry>` with `fill` +
`stroke` + `stroke-width`, nothing else — no filters, no `<linearGradient>`,
no drop-shadow `<feDropShadow>`. `--scale` expands the SVG's own canvas
coordinates (width, height, radius, stroke all multiply together), so a
scaled kit is the same shape rendered at a bigger size, never a raster
blow-up. State colour comes only from a fixed multiplier on the item's
base palette role (`pressed` × 0.78, `hover` × 1.12, `disabled` blended
50 % toward mid-grey) — the geometry never changes between states.

**Avoid.** Gradients, shadows, bevels, more than one stroke width in a
single item, a state that moves or resizes the shape, text baked into the
PNG (labels are a runtime overlay).

**Tooling.** `rsvg-convert` (librsvg) rasterizes the SVG and is REQUIRED —
`ui-draw.py` fails closed with a clear error (`rsvg-convert (librsvg) not
found — required for --style flat-vector; run ./install.sh --deps`)
rather than falling back to ImageMagick's own built-in SVG delegate,
which does not reliably render an unfilled (`fill="none"`) stroked shape
(confirmed directly on ImageMagick 7.1.2-26: a bars `frame`, which is
exactly that shape, came out fully transparent). There is no lower-
fidelity fallback path on purpose: a silently-broken `frame` is worse
than a stopped run. `--style pixel` never touches an SVG renderer and has
no `rsvg-convert` requirement at all.

**Window's title bar drives its own top slice.** A panel `window`'s
title-bar strip sits below the generic `(radius+stroke)*scale` corner
inset (it is ~14% of the panel's own height, a fixed floor at `stroke+4`)
— so `slices.json`'s `top` for `window` is
`max((radius+stroke)*scale, title_bar_bottom)`, not the plain generic
value every other item gets. Using the generic value alone would let a
9-slice engine's vertical stretch tear right through the middle of the
title bar the moment it needs to grow past the corner radius. Geometry
that would leave no positive band under the title bar is rejected before
any rendering (same "reject, never clamp" rule as everywhere else in this
script) — `tooltip` has no title bar and always uses the plain generic
inset.

**QA cues.** `magick identify -format '%[channels]'` on a panel or button
shows an alpha channel with `0` in the four corners and `255` at the
centre; a bar's `frame` border is itself opaque (sample a pixel just
inside the stroke, not the centre — the centre is transparent by design
and proves nothing about whether the ring rendered); `frame` and `fill`
share the exact same width/height as each other and `fill`'s bounding box
never overlaps `frame`'s stroke ring (see the pixel style doc for why
"never touches" is not the requirement — flat-vector keeps a visible 2px
gap on purpose, its canvas is large enough to afford one); `pressed` is
visibly darker than `normal` at the same crop, `hover` visibly lighter,
`disabled` visibly desaturated — same silhouette, three different fills;
`window` carries a title-bar strip that `tooltip` does not, and that
strip's pixel HEIGHT is unchanged by a 9-slice expansion at any factor
(measure it before/after — a strip that grew means the slice geometry
regressed).
