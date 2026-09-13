# Three.js / GLSL in authored HyperFrames video

This local contract is an opt-in graphics layer for create-tour, create-ad
(including an explicitly approved study) and HyperFrames create-explainer-video.
It is not a new renderer, an Assistant timeline feature, model-generated footage
or permission to invoke external workflows. Motion Canvas and other leaves do
not inherit it. Omitted `graphics` preserves old forms and frozen artifacts.

## Selection and provisioning

Carry `graphics: three-webgl2` in the actual approved tour form or ad/explainer
plan. No other value, including null, is supported. Explainer still selects
`renderer: hyperframes` and its v1 plan. Tour requires explicit `screen_mode`
and its v3 content approval; Three tours always require approved-preview even
if an old caller requests `preview: no`. Other proposal/preview/budget gates
remain unchanged. A graphics-mode change needs new source and approvals.

The maintainer provisions the dedicated runtime explicitly:

```sh
node hermes/engines/three-webgl/setup.mjs --browser <installed-dedicated-Chromium>
```

It pins Three.js 0.185.1, esbuild 0.28.2, puppeteer-core 25.10.0 and its own
HyperFrames 0.8.35 via package-lock, without using the mutable global CLI. Node,
browser bytes/version, runtime sources, built assets and CLI/core bundles are
recorded. A macOS app or chrome-headless-shell bundle is cloned separately;
no owner profile/cookies or existing CDP session is used. Every render opens an
isolated browser. ANGLE/SwiftShader software rendering is fixed for repeatability,
not maximum speed. Do not silently try hardware. `--refresh` is a maintainer
operation for source changes with the same dependency lock; it invalidates old
previews. Jobs never install, refresh, fetch libraries or change pins. Missing
or drifted runtime is a named blocker, not an optional-document fallback.

Before content approval, stage installed assets into the new source assets
directory. This copies real local files only, not layout or rendered media:

Read this reference through `video-creator-pipeline`. In the command below,
`${HERMES_SKILL_DIR}` is that lookup's returned pipeline directory, not the
selected create leaf or the last craft skill. Use the actual returned path;
never substitute a fixed live-home path when working in a candidate checkout.

```sh
~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/scripts/three_graphics.py" --assets <absolute-new-source-assets-directory>
```

The directory must exist and contain none of the reserved Three filenames.
The map includes `three-runtime.js`, `three-layer.js`, `THREE-LICENSE.txt` and
`three-runtime.json`. Include all four in the proposal inventory; never replace
their bytes or omit the license. The descriptor has no private machine paths.
Helpers verify hashes and the adapter's reviewed source before granting any
vendor-only exemption from the authored-code clock/network scan.

## Authoring contract

Keep the leaf's sized standalone root, copy/media rules and opaque background.
Add `data-hermes-graphics="three-webgl2"` and exactly one canvas inside it.
Load local GSAP, `assets/three-runtime.js`, then `assets/three-layer.js` before
task-authored scene code. All assets stay local.

```js
const tl = gsap.timeline({paused: true});
window.__timelines ||= {};
window.__timelines.ad = tl; // use this leaf's actual root id
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 50);
// Author actual geometry, materials, lighting and absolute-time state here.
HermesThree.mount({canvas, scene, camera, timeline: tl, update(time) {
  // Derive state from this time or GSAP's sought values, never prior-frame deltas.
}});
```

The helper owns WebGL2 creation, pixel ratio 1, root dimensions, preserved
draw buffer, sRGB output and NoToneMapping. It seeks the same paused GSAP
timeline, invokes update(time), draws, and finishes GPU work synchronously.
It participates in hf-seek and the installed render hook: suppressed GSAP
callbacks are never the only redraw trigger. Do not replace those hooks,
audit state or renderer clock. No rAF, setAnimationLoop, input-driven controls,
wall clock, random visual state or history-dependent postprocessing. Repeated
and backwards seeks must reconstruct the same frame.

Core procedural geometry/materials and custom ShaderMaterial GLSL are supported.
Put shader strings in authored JS; no render-time shader fetch or raw .glsl
loader exists here. Express time/progress as uniforms. For sRGB capture, write
linear working-space color and use Three output chunks (colorspace_fragment;
tone-mapping chunk where applicable). Keep copy in DOM elements so exact-copy
and text audits operate. Async model/HDR/texture loading, addons, OrbitControls,
WebGPU, multi-canvas compositions and another animation runtime are not implied
by the Three name. Ask for the missing capability rather than flattening it.
Source scans and a local server are not a sandbox for untrusted downloaded code.

## Evidence and quality

Use ordinary freeze/snapshot/render commands, not a direct CLI bypass. They
select the pinned CLI/browser/software mode only for this opt-in. Preview binds
runtime identity and graphics.json; render checks both, repeats the layer audit
in a new browser and requires byte-identical sampled layer PNGs. The audit seeks
forward, backward and forward again and checks actual SwiftShader draw calls,
programs and retained errors. Failures retain graphics.log; graphics-worker.json
is lifecycle bookkeeping, not visual proof. Browser errors in the real
HyperFrames command log fail even if the CLI returns zero. Software ReadPixels
stall warnings stay in evidence; do not suppress them to report a clean log.
Nonempty command stderr is retained alongside the primary evidence as
`<evidence>.stderr.log`, including the timeout path.

Layer equality is not whole-film acceptance. Inspect encoded video samples and
critical intervals: parallax must change near/far relationships, occlusion must
preserve geometry, and the shader boundary must travel through the surface,
not merely crossfade. Inspect actual UI crops at native/use size: shared edges,
spacing, icon weight, baseline alignment, selected/pressed state, foreground
layering and contrast. A strong hero shape cannot excuse a missing icon or a
generic control substituted for the design. Deliberately plain or faithful UI
remains valid. Do not use elaborate effects to hide weak parts.

Record what was inspected and at which time/size in qa.md before the next look.
Normal-speed viewing, dense sampling, a full decode and numeric geometry/pixel
checks are different evidence. Never claim continuous viewing or artistic
approval from a contact sheet or hash. Keep existing correction allowances,
user approvals and source versions.
