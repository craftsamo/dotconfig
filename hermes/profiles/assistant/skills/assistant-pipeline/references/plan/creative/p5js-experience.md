# p5.js experience — decision surface

Generative art, interactive canvas/WebGL experiences, custom data
visuals, audio-reactive sketches — browser-native, seeded,
reproducible. Timeline-driven video → `html-motion.md`; math
teaching → `manim-explainer.md`.

Technic `creator-p5js-experience` · QA `browser-media` ·
deterministic, zero generation spend · resident-only.

## Fix before release

- Concept and mode: generative still/animation, interactive
  experience, data visual, shader work.
- Canvas/viewport, pixel density, and the target browsers/devices;
  responsive behavior.
- Interaction model: which inputs (mouse, touch, keyboard, mic) and
  the accessibility/no-interaction fallback.
- Reproducibility: seeded (default — same seed, same output) vs
  deliberately live; performance floor (fps at target size).
- Deliverables: the runnable self-contained HTML is ALWAYS one;
  name any PNG/SVG/GIF/MP4 exports.
- For data visuals: the data source and its fidelity invariants.
- Offline/CDN policy: vendored p5.js vs approved CDN.

## Defaults

- Anchor: an approved hero state (seed + params screenshot) for
  styled sets or exhibitions; none for a quick sketch.
- Budget shape: zero generation; exports are mechanical.
