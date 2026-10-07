# Pixel animation — decision surface

Legacy only: use after Creator confirms this method, per [index](index.md).
Never use it as a fallback for a served failure or unsupported field.

Sprite/cel motion, procedural pixel loops, parallax, pixel MP4/GIF.
Never ordinary AI video with a retro prompt — that is
`generated-video.md` and it will not survive pixel QA.

Technic `creator-pixel-video` · QA `pixel-video` · deterministic
native-grid animation · resident-only.

## Fix before release

- The source: an existing pixel asset or a preceding `pixel-art.md`
  part (a composite: art part → animation part).
- One motion statement: what changes, what stays fixed
  (protected regions), and why the motion exists — story/character
  action needs a cel/sprite plan approved first.
- Native grid, duration, and cadence: effective unique
  frames/second vs container fps, chosen for this motion; loop or one-shot —
  a loop is a true cycle, verified at the wrap.
- Delivery: RGB-lossless master, compatibility copy, GIF — which
  ones, at what integer scale, size caps.

## Defaults

- Anchor: the palette + a contact sheet of first frames approved
  before the full frame run.
- Budget shape: zero generation for hand/procedural frames;
  camera/parallax moves in integer pixel steps only.
