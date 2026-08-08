# ASCII video — decision surface

Timed ASCII motion: video-to-ASCII conversion, audio-reactive
meters/scenes, generative animation, hybrid pieces, lyric videos,
TTS-backed delivery. Static ASCII → `ascii-art.md`.

Technic `creator-ascii-video` · QA `ascii-video` · deterministic
Python/ffmpeg render, zero generation spend (supporting TTS/media
are separate budgeted parts) · resident-only.

## Fix before release

- Mode + its source: video-to-ASCII (source video), audio-reactive
  (source audio), lyrics (audio + timed text), generative (declared
  generator), hybrid, TTS-backed (final script → a `voice.md` part
  first).
- Text geometry: cell size, character set, palette/color rule — and
  the destination (terminal vs encoded MP4/GIF) with output
  dimensions.
- Temporal contract: frame rate, duration, scene changes, audio
  sync, loop/GIF requirements.

## Defaults

- Anchor: representative keyframes approved before the full render.
- Budget shape: zero generation; supporting TTS counts on the
  `voice` line.
