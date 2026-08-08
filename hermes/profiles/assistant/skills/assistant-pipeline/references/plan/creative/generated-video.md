# Generated video — decision surface

Model-generated clips: text-to-video, image-to-video,
reference-guided. Deterministic HTML timelines → `html-motion.md`;
pixel animation → `pixel-video.md`; math explainers →
`manim-explainer.md`; editing existing footage → `media-assembly.md`.

Technic `creator-generated-video` · QA `video` · metered
`video_generate` (expensive, slow) · resident-only.

## Fix before release

- Destination + playback contract: exact duration, aspect,
  resolution, container/codec, size cap — and autoplay/mute/loop/
  poster requirements (web heroes autoplay muted; a seamless loop is
  built in post, not assumed).
- Strategy: **image-to-video** (a brand still/first frame exists —
  keeps identity) vs **text-to-video** (concept/atmosphere) vs
  **reference-guided** (identity across shots). Brand work defaults
  to image-to-video; fix the source stills/reference frames.
- One motion statement: camera move OR subject motion, pacing — not
  both at once.
- Audio: usually NO for web (muted autoplay; strip in post); social
  with native audio is backend-dependent — ground with an advisory
  before promising sound.
- **Text in video: no** — generated on-screen text warps; titles/
  captions are a post overlay (`html-motion.md`) or assembly stage.
- People/faces: prefer image-to-video from a fixed still, short
  shots, locked framing — or decide to avoid faces.

## Defaults

- Anchor: REQUIRED beyond one cheap clip — one short low-cost proof
  (4–6 s) before any set or long render (`asset-set.md`).
- Budget shape: 2 renders per asset, 1 corrective pass. GIF only
  where the destination demands it (chat, README) — otherwise
  mp4/webm.
