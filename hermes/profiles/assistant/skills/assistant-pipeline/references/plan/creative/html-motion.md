# HTML motion — decision surface

Deterministic motion graphics authored in HTML/CSS/JS (HyperFrames):
product/site tours, typographic motion, overlays, captioned videos,
social promos — rendered to exact MP4/WebM. Generative canvas art →
`p5js-experience.md`; model-generated footage → `generated-video.md`.

Technic `creator-html-motion` · QA `browser-media` (+ `video` for
the export) · deterministic render, zero generation spend
(supporting TTS/images/music are separate budgeted parts) ·
resident-only.

## Fix before release

- The narrative: scenes/tracks, what each scene shows, and the hero
  frames worth designing first.
- Design tokens: palette, type, spacing — from the brand or fixed
  here; motion character (calm/energetic, easing language).
- Delivery contract: duration, fps, aspect/resolution,
  container/codec, size cap, safe areas.
- Audio/captions: whether narration (a `voice.md` part), music
  (`audio-generation.md` part), or captions ride the timeline — each
  is its own part; this unit consumes them QA-passed
  (`composite-media.md` shapes the whole).
- Timeline discipline: deterministic, finite, seekable — no
  wall-clock or unbounded loops; fix the loop/end behavior.

## Defaults

- Anchor: the first hero frame (static layout) approved before
  animation work.
- Budget shape: zero generation for the render itself; draft render
  → final render is the loop, priced in turns.
