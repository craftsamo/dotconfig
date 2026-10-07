# HTML motion — decision surface

Enter only through the confirmed legacy route in [index](index.md).

This leaf is legacy-only, and only AFTER a Creator coverage check
([Client plan](../../SKILL.md)): authored UI tours, ads, and
launch/promo/brand motion or kinetic type up to 60 s (create-tour,
create-ad, create-promotion) that Creator's hands cover are handled by a
Creator brief, with no
assistant-side parts or Backend decisions. What follows is the
canonical technic for genuinely broader authored motion, or work the
user explicitly asks be planned this way.

Deterministic motion graphics authored in HTML/CSS/JS (HyperFrames):
product/site tours, typographic motion, overlays, captioned videos,
social promos — rendered to exact MP4/WebM. Generative canvas art →
`p5js-experience.md`; model-generated footage → `generated-video.md`.

Technic `creator-html-motion` · QA `browser-media` (+ `video` for
the export) · deterministic render, zero generation spend
(supporting TTS/images/music are separate budgeted parts) ·
resident-only.

Backend is fixed as `external:hyperframes`. It is the implementation engine
behind `creator-html-motion`, not an image/video generation alternative.
Every generated supporting asset is a separate unit with its own canonical
technic, Backend, and Budget.

## Fix before release

- The narrative: scenes/tracks, what each scene shows, and the hero
  frames worth designing first.
- Design tokens: palette, type, spacing — from the brand or fixed
  here; motion character (calm/energetic, easing language).
- Delivery contract: duration, fps, aspect/resolution,
  container/codec, size cap, safe areas.
- Audio/captions: whether narration (a Creator brief for
  audio-creator's `generate-speech`, approved script required), music
   (a finished supplied track or separately approved Creator-brokered
   music delivery), or captions ride the timeline — each
  is its own part; this unit consumes them QA-passed
  (`composite-media.md` shapes the whole).
- Timeline discipline: deterministic, finite, seekable — no
  wall-clock or unbounded loops; fix the loop/end behavior.

## Defaults

- Anchor: the first hero frame (static layout) approved before
  animation work.
- Budget shape: zero generation for the render itself; draft render
  → final render is the loop, priced in turns.
