---
name: creator-p5js-experience
description: >-
  Creator's deterministic leaf technic for p5.js generative art,
  interactive browser experiences, data visuals, shaders, and exported motion.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, p5js, generative-art, interactive, webgl, canvas]
    category: technic
---

<Goal>
Produce a reproducible browser-native visual whose concept, seed, interaction,
performance, and exported artifact survive review. The canonical dispatch
identity is `creator-p5js-experience`; the official `p5js` skill is its
implementation engine.
</Goal>

<Scope>
Use for generative art, interactive canvas experiences, custom data
visualization, browser animation, WebGL/shaders, image processing, and
audio-reactive p5.js work. Route deterministic timeline-driven video to
`creator-html-motion`, educational animation to `creator-manim-explainer`, and
model-generated clips to `creator-generated-video`.
</Scope>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
- Load `skill_view(name="p5js")`; do not copy its references or expose `p5js`
  as the stable dispatch identity.
- A self-contained HTML source is always a deliverable. PNG, SVG, GIF, or MP4
  exports are additional deliverables named by the brief.
- Deterministic browser rendering has zero generation spend. Supporting image,
  video, TTS, or generated audio uses its own canonical technic and Budget line.
- Never install a browser, Node package, font, or system dependency. A missing
  preview/export path blocks production.
</Contract>

<Preflight>
Check the official skill resolves, the requested p5.js version and add-ons are
available from an approved CDN or vendored locally, and the target browser can
run the sketch. For automated still or frame export, require Node.js plus a
working headless Chromium/Puppeteer path; MP4 additionally requires `ffmpeg`.
Validate local assets, fonts, CORS/server needs, output permissions, viewport,
pixel density, interaction devices, and destination browser support.
</Preflight>

<Procedure>
1. Lock the concept, mode, canvas/viewport, renderer, interaction model, seed,
   palette, motion vocabulary, performance target, and export formats.
2. Load the official engine and write one project HTML file. Separate immutable
   configuration and palette from mutable state; seed every visual random/noise
   path and record any deliberately non-deterministic input.
3. Run the real page at target size. Fix console errors, missing assets, resize
   behavior, touch/keyboard/mouse paths, frame-rate misses, and WebGL fallback
   behavior before export.
4. Capture representative states, including interaction and animation extrema.
   For deterministic frame export, let the capture script advance one frame at
   a time; never race a free-running draw loop.
5. Export the requested formats, preserve the exact source, assets, seed,
   parameters, commands, logs, and previews, then hand them to pipeline V1-V6.
</Procedure>

<Verification>
- The HTML opens without console/runtime errors and renders the intended first
  frame at the target viewport; local assets and fonts resolve without hidden
  network assumptions.
- Repeating the same seed and parameters reproduces the same inspected states.
- Every required interaction works with its named input method, resize behavior
  is intentional, and sustained performance meets the brief.
- Export dimensions, format, duration/fps, alpha, and file-size cap are measured.
  Inspect stills or multiple spread frames rather than accepting a successful
  capture command as visual proof.
- Attach the runnable HTML and required assets as the reusable master, plus only
  the requested final exports.
</Verification>
