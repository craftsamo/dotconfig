# video-creator: ad

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-ad` — a short authored ad (HyperFrames project, proof frames, MP4) from a product, audience, one message and CTA, with supplied assets and optional audio.
- `analyze-ad` — reads one local short ad (up to 60 s) as a creative reference or reviews its message, evidence, typography, pacing and call to action; a timestamped breakdown, no new ad.

## Range

- 6–30 s (default 15); aspects 9:16 (default), 16:9, 1:1, 4:5, each authored on its own canvas; 24–60 fps (default 30).
- One headline message that appears verbatim, and a final CTA held on screen; claims stay within what the client supplies.
- Looks come in three layers: `theme` (world), `style` (presentation), `direction` (how message, claim and CTA stage and pace); each takes a described value as well as a listed one. An optional `graphics: three-webgl2` layer adds Three.js/GLSL depth.
- Product and logo come from supplied assets, never invented; a text- or graphics-only ad is possible. Picture shots drawn by a video model can be added as muted clips, but never stand in for the real product.
- `purpose: study` is a short diagnostic piece of 1–10 s on one visual or motion question; not final media.
- Audio is supplied (finished WAV or cue list) or a finished Mix master; the leaf does no speech synthesis.
- The proposal and preview are separate stages before the final render.

## Where directions go

- Authored video: the producer writes the storyboard. The direction travels in `note` (plus `theme`, `style`, `direction`, `theme_detail`) with named techniques from video-creator's `references/motion-vocabulary.md`: `skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary.md")`; depth work: `references/three-graphics.md` in the same skill.
- Option vocabulary: one file per option under `references/themes/`, `references/styles/`, `references/direction/` of `create-ad`, e.g. `skill_view(name="create-ad", file_path="references/direction/claim-led.md")`.

## Boundaries

- Introducing a brand, world or qualities without one action: [promotion](promotion.md). UI task walkthrough: [tour](tour.md). Learning goal: [explainer-video](explainer-video.md).
- Shots drawn by a model: [clip](clip.md). Soundtrack: [mix](../audio-creator/mix.md).

## Examples

No stored example; propose the leaf's representative sample unit: a short study (1–10 s) of one visual question, or a draft of one ratio from the content plan.
