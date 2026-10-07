# ASCII video — decision surface

Legacy only: use after Creator confirms this method, per [index](index.md).
Never use it as a fallback for a served failure or unsupported field.

Timed ASCII motion: video-to-ASCII conversion, audio-reactive
meters/scenes, generative animation, hybrid pieces, lyric videos,
TTS-backed delivery. Static ASCII → `ascii-art.md`.

Technic `creator-ascii-video` · QA `ascii-video` · deterministic
Python/ffmpeg render, zero generation spend (supporting TTS/media
are separate budgeted parts) · resident-only.

## Fix before release

- Mode + its source: video-to-ASCII (source video), audio-reactive
  (source audio), lyrics (audio + timed text), generative (declared
  generator), hybrid, TTS-backed (a Creator brief for audio-creator's
  `generate-speech` first, approved script required — the technic
  consumes the completed delivery, never synthesizing it itself).
- Text geometry: cell size, character set, palette/color rule — and
  the destination (terminal vs encoded MP4/GIF) with output
  dimensions.
- Temporal contract: frame rate, duration, scene changes, audio
  sync, loop/GIF requirements.

## Defaults

- Anchor: representative keyframes approved before the full render.
- Budget shape: zero generation; a supporting speech delivery is
  audio-creator's own take grant, accounted for separately.
