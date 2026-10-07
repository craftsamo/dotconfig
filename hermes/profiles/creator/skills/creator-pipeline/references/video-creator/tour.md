# video-creator: tour

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-tour` — a bounded UI task walkthrough (HyperFrames project, proof frames, MP4): recreated UI, supplied footage, or an isolated capture of a sanitized Web demo.

## Range

- At most 60 s (default 20) including intro and outro; 1280x720 landscape or 720x1280 portrait; 24–60 fps.
- `screen_mode`: recreate (default), supplied, capture. `fidelity`: faithful (default, preserves the product UI) or simplified.
- Presentation: `frame` (macos, browser, ios, android, none), `style` (flat, glass, outline), `background` (light, dark) with an optional backdrop image; none of it reskins the product UI.
- Intro and outro are on by default (examples: title-reveal, ui-overview, result-first; result-hold, overview-close, next-action); free text is first-class.
- Narration is a finished audio-creator delivery or Mix master; the leaf does no speech synthesis. An optional `graphics: three-webgl2` layer adds depth.
- Capturing a URL or app needs separate consent for the target and its scope. Native macOS capture and login recording are unavailable.
- Not expressible: marketing films, browser automation, image generation.

## Where directions go

- Authored video: the producer writes the storyboard. The direction travels in `note` (plus `flow`, `style`, `intro`, `outro`) with named techniques from video-creator's `references/motion-vocabulary.md`: `skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary.md")`; depth work: `references/three-graphics.md` in the same skill.
- Option vocabulary: one file per option under `references/styles/`, `references/intro/`, `references/outro/`, `references/screen-mode/` of `create-tour`, e.g. `skill_view(name="create-tour", file_path="references/intro/title-reveal.md")`.

## Boundaries

- Brand or launch motion: [promotion](promotion.md). A claim and CTA toward an action: [ad](ad.md). A topic with a learning goal: [explainer-video](explainer-video.md).
- Trimming supplied footage as it is: [clip](clip.md).

## Examples

No stored example; propose the leaf's representative sample unit: a short storyboard-approved draft of one task, with preview frames before the full render.
