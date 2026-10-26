# neon

**Look.** The subject as bent glass neon tubing: one continuous
glowing line of even width with rounded ends, a bright near-white core
and a saturated coloured halo, one or two tube colours, no mounting
clips (the cut-out would erase them). The glow needs
darkness and the corner-flood cut-out is hard-edged, so `<bg>` is always
a very dark flat colour, never white. Soft glow: `background: #rrggbb`
(dark) with that same hex as `<bg>`, finished with `icon-finish.sh
--background <hex> --keep-bg --pad 0` (the model's own dark square fills
the icon, no seam). `transparent` or `tile` use `<bg>` `#101014` and the
usual finish; they keep the tube with a clipped halo.

**Prompt block.**
> neon sign icon of <subject>, bent glass neon tube in <palette>, one
> continuous glowing line of even width, bright white-hot core with a
> saturated coloured glow halo, rounded tube ends, minimal simple
> shape, centred on a plain flat very dark <bg> background, no text, no
> watermark, no brick wall, no mounting clips

**Avoid.** A brick wall or sign board behind (the halo becomes part of
the scene), text or letters, thin double tubes that merge at small
sizes, a halo so wide it fills the canvas, promising a soft glow on
`transparent` (the cut-out clips it into a ring — say so before the
spend and offer the dark square).

**QA cues.** The tube line stays one clean stroke at 32 px; the core is
brighter than the halo; a `--keep-bg` result is one even dark square
whose halo fades smoothly with no hard ring; a transparent or tile
result is expected to show a clipped halo and is reported as such,
not hidden.
