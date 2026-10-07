# Commission — video-creator: pixel-animation

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a grid-exact pixel animation (cel cycle, character loop, logo or scene loop, effect, integer-step parallax) as a lossless master MP4 plus a compatibility MP4 and optional GIF | `create-pixel-animation` | free, deterministic, fixed palette, numerically verified cadence and loop seam |

## Choosing and filling

Grid-exact pixel motion is this leaf. A model-made clip with a pixel look is
not: that is `generate-clip` with the `pixel` style, which guarantees neither
grid, palette nor cadence.

Settle with the user:

- **Purpose** → `what_for`.
- **Grid** → `grid`, the native size (e.g. 32x32).
- **Motion statement** → `motion`: what moves, what stays fixed (the
  protected regions) and why.
- **Cadence** → `effective_fps` (unique frames per second, default 10) and,
  if known, `frames` per cycle or `duration`.
- **Loop** → `loop`: a seamless cycle (default) or a one-shot.
- **Outputs** → `scale` (integer, default 8) and `gif` (default no); the
  lossless master and the compatibility MP4 are always delivered.
- **Content** → `source` (a native pixel PNG or a create-pixel-art
  delivery) or `subject` (poses and features) when there is none.

A still made first is its own [pixel-art](pixel-art.md) unit; its delivery
(the native PNG or the delivery directory with `palette.json`) becomes
`source` of this unit, so the palette carries over.

## Transport

`kind="work"`: cels, encoding and verification are several files and
commands.

## Round-trip and approvals

No proposal round. A revision is `intent: revise <path of the previous
delivery>` with the change only; the hands keep the previous cels and palette.
