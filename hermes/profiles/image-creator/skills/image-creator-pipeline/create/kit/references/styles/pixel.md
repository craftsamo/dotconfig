# pixel

**Look.** A tiny logical bitmap (buttons 48×16, panels 96×64, bars 64×8)
drawn pixel-by-pixel with hard binary edges — no anti-aliasing, no
sub-pixel coverage — then upscaled by an integer `--scale` with
nearest-neighbour so every source pixel becomes one crisp square block.
The default radius is 0 (a square widget); a non-zero radius still reads
as stepped, blocky corners, never a smooth curve — that stepping is the
pixel-art look, not a defect. The 16-bit era UI-chrome family.

**Drawing rules.** Every pixel is a plain inside/outside boolean test
against the rounded-rect geometry (never a fractional coverage value), so
a corner pixel is either fully opaque or fully transparent — nothing in
between. The border band is the ring between the outer and an inner
rounded rect inset by `--stroke`; a filled item's interior uses the fill
colour, an outline-only item (a bar's `frame`) leaves its interior fully
transparent. A bar's `fill` is a SEPARATE, inset shape (never the same
raster as `frame` with the interior filled in) — it never draws a stroke
ring of its own, so it never overlaps `frame`'s stroke. Unlike
flat-vector, pixel's `fill` inset equals `frame`'s own stroke EXACTLY
(`BAR_FILL_PAD_LOGICAL["pixel"]` is `0`) — it fills the whole hollow
interior right up to the border, touching it, with no extra gap. That is
intentional, not a lesser version of flat-vector's look: a pixel bar is
only 8 logical px tall, so flat-vector's 2px extra gap would leave a
2px-tall (25%) sliver of visible fill; touching the border instead keeps
6px (75%) — non-overlap is the only real requirement, a visible gap is
not. A panel's `window` gets a title-bar strip painted only over its
already-filled interior pixels (so it automatically respects the rounded
corners); `tooltip` does not, and is otherwise identical. `--scale` is
applied AFTER the logical bitmap is complete, with `-filter point`
(nearest neighbour) — never a smoothing filter, never applied to the
logical coordinates before drawing.

**Avoid.** Any antialiased or partially-transparent edge pixel, a smooth
curved corner, scaling with a filter other than nearest/point, a
non-integer `--scale`, a bar `fill` that reuses `frame`'s stroke ring
instead of drawing its own inset shape (that regresses to a fill that
overlaps the frame's border, not merely one with a smaller/no gap).

**QA cues.** Zoom into a scaled PNG: every block of `scale × scale`
output pixels is one flat colour (no gradient inside a block — that would
mean a smoothing filter was used). A corner pixel with `--radius > 0`
reads `alpha=0` (`magick identify -format '%[pixel:p{0,0}]' file.png` on a
rounded item's PNG). The interior of an unfilled item (`bars` `frame`) is
fully transparent, not a faint tint. `frame` and `fill` share the same
width/height; `fill`'s opaque bounding box never extends past `frame`'s
own hollow interior (non-overlap, checked via each PNG's own alpha plane
— NOT via a required visible gap between them: at the default stroke,
`fill` legitimately starts exactly where `frame`'s stroke ends). `fill`'s
opaque height should be a large majority of the canvas (≥ 50%), not a
thin sliver — a regression back to flat-vector's 2px gap constant would
shrink a default 8px-tall bar's fill to 25%. `window` and `tooltip`
differ (their bytes are not equal); a pixel inside `window`'s title-bar
region is the accent colour, the same pixel in `tooltip` is not.
