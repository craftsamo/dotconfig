# ASCII art — decision surface

Static terminal-safe text art: banners, message characters, framed
text, image-to-ASCII, sourced premade art. Anything timed or
audio-reactive → `ascii-video.md`.

Technic `creator-ascii-art` · QA `ascii-art` · deterministic, zero
generation spend · card: `deterministic-render` for settled
conversions.

## Fix before release

- Mode: text banner / message character / framed text / ANSI
  banner / image-to-ASCII / sourced premade / freeform custom.
- Destination terminal geometry: width × height budget the art must
  fit, and the monospace font assumption.
- Glyph set (pure ASCII vs UTF-8 blocks) and the ANSI-color rule —
  plain UTF-8 master by default, ANSI only when the destination
  really renders it.
- For image-to-ASCII: the source image; for sourced art: the source
  + attribution expectation.

## Defaults

- Anchor: none — deterministic.
- Budget shape: zero generation. The UTF-8 text master is the
  deliverable; a PNG preview accompanies it when layout risk exists.
