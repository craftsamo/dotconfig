# video-creator: pixel-animation

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-pixel-animation` — a grid-exact pixel animation: sprite or cel cycles, character loops, logo or scene loops, environmental effects and integer-step parallax, delivered as an RGB-lossless master MP4, a yuv420p compatibility MP4 and an optional GIF; nothing generated.

## Range

- Any native `grid` `WxH`; a fixed palette (from a `source` native PNG or a create-pixel-art delivery, or drawn from a `subject`); `effective_fps` (unique frames per second, default 10) held equally in the container; a seamless `loop` (default) or a one-shot; integer `scale` (default 8) and optional `gif`.
- Measured, not promised: grid and scale, palette, cadence and loop seam are checked numerically on the encoded files, so it suits sprites, avatars, logo and scene loops, rain, snow, embers and stepped parallax.
- Named techniques from video-creator's `references/motion-vocabulary.md` (`skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary.md")`) apply where they can be stepped on the grid (squash and stretch, anticipation, a camera push as integer shifts); smooth easing, blur, rotation and sub-pixel moves do not exist here.
- It does not suit photographic or painterly motion: a model-made clip with a pixel look is `generate-clip` and guarantees no grid.

## Where directions go

- `motion` fixes what moves and what stays fixed; `grid`, `frames`, `effective_fps`, `duration` and `loop` fix the timing; `source` or `subject` carries the content; `scale`, `gif` and `note` fine-tune.

## Boundaries

- A still to animate comes from [pixel-art](../image-creator/pixel-art.md) first, or from the user.
- Model-generated motion: [clip](clip.md).

## Examples

No stored example; propose the leaf's representative sample unit: a small loop of a few cels on a 32x32 grid.
