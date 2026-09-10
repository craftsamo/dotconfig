# Local UI Authoring

Author HTML/CSS/GSAP for this task, not a generic scene DSL. Screenshots and
designs are evidence for UI facts; text alone can be sufficient. Choose layout
for readable video. Creator settles missing semantics, not coordinates.

## Ownership and Style

Frame = outer device/window chrome. Background/backdrop = decorative world
behind it. Style = presentation treatment, including explanatory callouts.
Faithful fidelity preserves the product's internal labels, controls and
relationships. Simplified fidelity permits approved omissions/recomposition;
record them in `fidelity_note`, label illustrative UI visibly, and never claim
an invented modal or setting is a real-product feature. Use one accent, a
restrained type scale (UI normally >=22 px at 720p), high-contrast text and
generous spacing. Custom style is authored locally, not registered globally.

## Source Contract

- One standalone `index.html` with a sized 1280x720 or 720x1280 `#root`,
  `data-composition-id="tour" data-start="0" data-width="1280"`
  `data-height="720" data-duration="20" data-fps="30"`. Adjust size/duration
  to the approved form. Root background is opaque; no template wrapper.
- Copy `assets/gsap.min.js`, `assets/GSAP-LICENSE.txt` and
  `assets/gsap-provenance.json` from this leaf's assets into source assets.
  Keep the license with the runtime. Other assets stay local under `assets/`;
   no remote imports, dependencies, event handlers or render-time capture. Local fonts or
  supplied WOFF2 are allowed. Do not fetch fonts. Declare named installed OS
  fonts with `@font-face` and `src: local(...)`; a font-family name alone does
  not satisfy the renderer. Verify the local face and Japanese glyphs. Keep
  all IDs unique.
- Build synchronously: `const tl = gsap.timeline({paused:true});`, author
  explicit time-positioned tweens, then
  `window.__timelines ||= {}; window.__timelines["tour"] = tl;`.
  No autoplay, clocks, timers, randomness, external requests, hover/scroll
  triggers or runtime DOM creation. Prebuild every state; seek it via timeline.
  Put frame-zero hidden states in CSS or immediate GSAP initialization, not
  only a paused `tl.set(..., 0)`; inspect frame zero and reverse seeking.
  A font-ready callback may check text bounds but must not build the timeline.
- Use `x/y/scale/rotation` for spatial motion, not width/top/left tweens.
  Set initial transforms on the timeline, not competing CSS transforms.
  Use `immediateRender:false` for later fromTo tweens on reused properties.
  Never tween display/visibility on framework-owned `.clip` elements.
- Keep one live UI wrapper through the task. Put pointer and targets in its
  coordinate space, or explicitly transform both. Click contact ignites the
  state change on the same frame. No unexplained camera ping-pong, idle wobble,
  filler drift or crossfades between unrelated screens. Establish full view,
  focus the action, pull back only to reveal context/result. Modal focus can
  blur the UI beneath, never the modal's text. Pause briefly before a major
  result, then hold it for reading. Intro/outro must integrate with this same
  carrier, not unrelated title-card slides. For separate scenes document
  matched exit/entry direction and velocity in task notes before authoring.
- Optional narration is already-finished audio-creator PCM WAV plus its current
  words sidecar. Validate with `tour.narration`, copy both locally and place an
  id-bearing `<audio>` with explicit start/duration. No synthesis here. Do not
  infer listening quality from its hash. A silent task needs no audio or SRT.
- Add `index.motion.json` using HyperFrames assertions such as
  `appearsBy`, `before`, `staysInFrame`, `keepsMoving` where they express real
  intent. Example: `{"duration":20,"assertions":[{"kind":"staysInFrame",
  "selector":"#window"}]}`. Do not silence whole scenes to appease QA.

## Freeze and Approval Contract

VideoCreator writes `contract.json`, NOT the client. It describes proof, never
drives layout or enumerates possible actions:

```json
{
  "duration": 20,
  "intro": {"direction":"title-reveal","start":0,"end":3,
    "description":"Readable title docks above the same UI as it is revealed"},
  "outro": {"direction":"result-hold","start":17,"end":20,
    "description":"Final selection stays visible with a concise completion line"},
  "fidelity_note":"Approved illustrative settings UI, not a capture or claim about macOS",
  "samples": [
    {"at":0,"expect":"First visible title"},
    {"at":1.5,"expect":"Title-to-UI transition"},
    {"at":7,"expect":"Pointer at selected control; UI state updated"},
    {"at":18,"expect":"Readable result and completion line"},
    {"at":19.966666666666665,"expect":"Final visible frame retains result"}
  ]
}
```

`direction` must equal the filled form exactly, including free text. A custom
request such as "Two light/dark tiles join into one settings window" is saved
verbatim with the concrete authored choreography in `description`; it is not
classified as title-reveal. Ask one clarification/propose a beat if ambiguous.
For explicit none, use direction `none`, empty description and a zero-length
interval at 0 for intro, total duration for outro. Missing fields default to
title-reveal/result-hold ON; empty/null is an error, not omission.

Include first/last visible frames, intermediate action states, contact frames
and transition proof times (3..40 sorted samples). Frozen form/source/contract
hashes bind preview approval. Changes require fresh source/project/preview.
Only `.hyperframes/` is renderer-owned cache; never put source there. Source
bundles are <=200 files/128 MB, individual files <=64 MB. Paths are absolute,
physical, symlink-free; outputs cannot live within frozen source/project.
On macOS use the physical `/private/var/...` or `/private/tmp/...` spelling,
not the system's `/var` or `/tmp` symlink alias. Resolve scratch roots before
passing them, never resolve away symlinks inside an authored asset tree.

The helper checks structure, bounds and direction equality. It cannot prove
JavaScript safety: its textual code scan names the offending file/token and
exempts only the hash-pinned `assets/gsap.min.js`. HTML visible copy is not code;
script/style contents, including their comments/string literals, are scanned.
Keep clock/API examples out of executable source when they trigger the guard.
It also cannot prove
that prose is faithfully choreographed: compare each actual frame to `expect`
and the approved reference. Check reverse seeking as well as forward playback
when developing complex state changes. Inspect final decoded MP4 samples and
record native-size text, glyph, contact, camera and state verdicts in `qa.md`.

## Spec-to-Render Review

Before freeze, map the approved frame, style, background, flow and literal
intro/outro directions to observable proof in the contract samples. After render,
record each verdict in `qa.md` with a decoded frame/time and any unmet requirement.
A matching form string, successful checker or OCR result is not a visual verdict.
Keep custom directions verbatim; judge their intended result, not preset membership.

Review the short sequence at normal speed when available, then inspect dense
native-frame samples around approach, arrival, contact, response and each boundary.
Choose sampling density for the motion (roughly 0.05-0.1 s for a quick UI event),
record actual frame indices, and never fabricate subframes. If normal-speed viewing
is unavailable, say so; automated 1x playback and still inspection are separate evidence.

Measure the target's size/position before and after camera travel: does the move
actually direct attention to the approved action, or only enlarge the whole screen?
Check pointer entry/exit continuity, approach duration and deceleration, transformed
tip contact, hover/press/release and contact-to-response timing. Check modal foreground
versus backdrop choreography, incremental text/caret alignment, saved state, result
hold and integrated opening/closing. Pair source geometry with decoded pixels; neither
alone proves the other. Do not impose a universal zoom count, centering rule, shadow
recipe or timing threshold. Report missing/uninspected reference evidence separately
from a failure to honor an explicit input. Return unresolved defects within the pass
budget; never silently alter must-keep choices to make checks pass.

## Compatibility

`scripts/tour.py` remains usable for actual persisted v1 projects and direct
v1 scaffold/snapshot/render calls. Its screenshot manifests, defaults, HTML
and approval records are not migrated. New authoring uses `scripts/authored.py`
and v2 integrity records. This seam preserves shipped artifacts without making
the old layout engine understand arbitrary UI or forcing old forms onto v2.

Explicit screen_mode uses v3 proposal approval; omitted mode still writes v2.
Supplied/captured footage uses the same authoring/freeze/preview/render seam,
with actual timed media and the source manifest described in its mode reference.
Raw captures and approval/source evidence are private; only prepared presentation
assets enter the frozen project, which is itself a private source deliverable.
