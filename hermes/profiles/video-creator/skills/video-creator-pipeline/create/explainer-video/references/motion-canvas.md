# Motion Canvas (`renderer: motion-canvas`, `version: 2`)

Motion Canvas is implemented and executable here. This reference covers what
is different about it; the common plan fields, `propose`/`freeze`/`snapshot`/
`render` lifecycle, and Creator-relayed approvals are exactly as described in
[authoring](authoring.md) — nothing about approvals changes for this engine.

## Choosing this engine

`renderer` is selected explicitly in the spec and preserved once made; there
is never a silent switch between engines, and never a switch on failure.
Internally, `renderer: motion-canvas` pairs with plan `version: 2`. Prefer
Motion Canvas for reactive diagrams, algorithms and Canvas-based explanation.
Prefer HyperFrames (`renderer: hyperframes`, `version: 1`) for HTML/UI or
media-oriented compositions. Motion Canvas does not require the external
HyperFrames technical references (the parent skill's

```text
skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
```

policy); this local reference stands in their place for Motion Canvas
source authoring.

An old `version: 1` plan that named `renderer: motion-canvas` before this
engine existed was discussion-only and stays non-executable — it can never
be resumed as-is. Rendering with Motion Canvas always requires a fresh
`version: 2` proposal and a new approval, never the old plan's hash.

## Source contract

The frozen source is an ordinary Motion Canvas project, not a HyperFrames
project:

- `scene.tsx` — a default export built with `makeScene2D`, importing
  `@motion-canvas/core` and `@motion-canvas/2d` normally.
- `scene.meta` — a JSON sidecar with keys exactly `version, seed, timeEvents`:
  `version` must be the integer `1`; `seed` is a fixed, explicit integer (no
  clock/random seed); `timeEvents` is a bounded (<=256) list of `{name,
  targetTime}` entries, each `targetTime` inside `0..duration`.

Everything else allowed in HyperFrames source stays allowed here too:
ordinary `.ts`/`.tsx`/`.js` modules, JSON, CSS, and the supplied images,
video and WOFF2 assets referenced from the plan's `assets` map. Not
allowed, and rejected at build time: any project `node_modules`, package
manifest or Vite config file, `?scene`/`?project`-style Vite query imports,
dynamic `import()`, clock- or `Math.random`-based randomness, or any remote
asset. Compilation rejects any import outside the frozen source and the
pinned runtime's own `node_modules` — this is trusted authored code, not a
sandbox for hostile JavaScript.

## Runtime: no Vite, no editor, no HMR

The runtime bundles the selected `scene.tsx` with esbuild and bootstraps
Motion Canvas 3.17.2 directly (`engines/motion-canvas/browser.ts`,
`render.mjs`) — there is no Vite dev server, no editor UI, no hot module
reloading, and no rewriting of source metadata; the frozen `scene.meta` is
attached to the scene exactly as supplied.

## The `@explainer/runtime` module

Source never talks to HyperFrames-style globals. Instead it imports the
virtual `@explainer/runtime` module, which exports:

- `plan` — the frozen, approved plan object.
- `copy(id)` — the approved on-screen text for a `copy` row id.
- `visible(id)` — `1` inside that row's approved `start..end` window, else
  `0`, evaluated against the current render time.
- `mouthOpacity(shape)` — `1` when `shape` is the active cue mouth shape at
  the current time, else `0`; throws for a shape not in `character.mouths`.
- `time()` — the current render time in seconds.

Use `time()` — never Motion Canvas core's `useTime()` — inside any
reactive visual or video property callback. `useTime()` is
generator-thread-only; calling it from a render-time property callback is
wrong even though it may appear to work. The provided `time()` instead
reads the view's own reactive `globalTime` signal, which is valid at
render time and invalidates cached visibility/video bindings every frame.

## Binding approved copy and character assets

- Every approved visible `copy` row is a `Txt` node with `key` equal to the
  row's `id`, `text={copy(id)}`, and `opacity={visible(id)}`.
- The character body, when `framing != none`, is an `Img` (still/puppet) or
  `Video` (animated) with `key="character-body"` and `src` equal to the
  plan's approved `character.body`/`character.video` asset path.
- Mouth images, when `lip_sync: cues`, are `Img` nodes keyed
  `character-mouth-<shape>` for each key in `character.mouths`, with
  `opacity={mouthOpacity(shape)}`.
- An animated character `Video`'s playback time is bound to the provided
  `time()`, with no looping and no retiming (playback rate stays `1:1`
  with the render clock) — no new lip-sync inference, speech generation or
  rig authoring happens here, exactly as for HyperFrames.

## What the runtime audits, and what it does not

At every rendered frame the runtime audits the actual visible `Txt` text
and its bounding window against the approved `copy` rows; at each proof
sample time it additionally checks that every row due to be visible
actually is, with matching text and an on-canvas bounding box. It also
checks that every visible image/video source is an approved plan asset,
that mouth-image states match the active cue, and that an animated
character video's playback time tracks the render clock. None of this
proves canvas contrast, occlusion, Japanese glyph correctness, factual
claims, or that anyone has listened to the result — canvas contrast in
particular needs a real visual review and must never be reported as an
automated pass. Any specialized drawn text not represented by a `Txt` node
(e.g. text baked into a canvas drawing) is invisible to this audit and
needs the same explicit visual review.

## Render output and audio

Native render output is a bounded PNG sequence, not a video file. The
existing FFmpeg mux step is reused unchanged to add only the approved
speech/Mix master; it never captures or exports browser audio. Before
that mux, the final render must reproduce the already-approved preview's
sample PNG hashes exactly, the same "no new render without a new preview"
discipline as HyperFrames. All the common final decode/audio checks in
[authoring](authoring.md) (`render`) still run unchanged.

## Bounds

- `duration` and every `samples[].at` must land exactly on the 30fps
  frame grid (`round(value * 30) == value * 30` within floating-point
  tolerance) — an off-grid value is rejected before any render.
- `duration` maximum is 180 seconds, same as HyperFrames.
- Source is capped at 200 files / 128 MB total; each individual file is
  capped at 64 MB.
- Derived frame output (the PNG sequence) is capped at 2 GB.
- A single render invocation has a hard 10-minute limit.

## Runtime provisioning

For an explicit runtime upgrade, first wait for owned renders to finish.
Preserve the existing ignored `hermes/local/motion-canvas` directory in a
maintenance backup, then run setup for a fresh runtime. The dedicated macOS
clone lives at `hermes/local/motion-canvas/browser/Renderer.app`; never patch
or overwrite its signed contents while a job is using it. Changed runtimes
require fresh preview approval, not edits to old source or approval hashes.

The runtime is provisioned explicitly by a maintainer, never by a job:

```sh
node hermes/engines/motion-canvas/setup.mjs --browser <installed-Chromium-executable>
```

run from the repository root, with Node >=22.12 and FFmpeg already
installed. Packages are installed into the gitignored
`hermes/local/motion-canvas`; no browser is downloaded by this step or by
any job. Jobs never install or upgrade anything — a missing or drifted
runtime is reported as a maintainer-provisioning gap, never worked around.

A supplied macOS `.app` browser is APFS-cloned automatically into the
gitignored `runtime/browser/Renderer.app` inside that runtime directory,
preserving the signed app's contents unchanged — a separate app identity
avoids a Dock/LaunchServices conflict with the maintainer's everyday
browser. A non-app dedicated Chromium/headless-shell binary is instead used
directly, in place. Neither path copies any cookies or profile data: every
render launches the browser against a fresh, isolated profile. Setup may be
rerun safely against the same pinned `package-lock.json` without
reinstalling dependencies, but it never overwrites a different already-
provisioned browser clone or a changed lock; that drift needs an explicit
maintainer replacement/fresh provisioning step and a new preview approval.

Every preview records the actual runtime/Node/browser identity used
(`render.mjs --identity`), checked again at snapshot/render time. A normal
browser version change does not by itself require rerunning setup — only a
changed pinned dependency lock or a missing/replaced clone does — but any
identity change still invalidates a previously approved preview, which must
be refreshed and re-approved before render. Do not claim a render or check
was performed if it was not actually run through this pinned runtime. Final
QA also carries the engine's contrast-audit status: Motion Canvas performs
no automated contrast check and always reports it as requiring a manual
visual review (see "What the runtime audits, and what it does not" above).

## Example

A small, genuine Motion Canvas scene using the provided helpers and
ordinary shapes — not a template to instantiate, just the shape of real
source:

```tsx
import {makeScene2D} from '@motion-canvas/2d';
import {Circle, Img, Txt} from '@motion-canvas/2d';
import {copy, time, visible, mouthOpacity} from '@explainer/runtime';

export default makeScene2D(function* (view) {
  view.add(
    <>
      <Img
        key="character-body"
        src="assets/character-body.png"
        x={-300}
        y={100}
      />
      <Img
        key="character-mouth-rest"
        src="assets/mouth-rest.png"
        x={-300}
        y={160}
        opacity={() => mouthOpacity('rest')}
      />
      <Img
        key="character-mouth-open"
        src="assets/mouth-open.png"
        x={-300}
        y={160}
        opacity={() => mouthOpacity('open')}
      />
      <Circle
        width={40}
        height={40}
        fill="#4da3ff"
        x={() => Math.sin(time() * 2) * 120}
        y={0}
      />
      <Txt key="c1" text={() => copy('c1')} opacity={() => visible('c1')} y={-200} fill="white" />
    </>,
  );
  yield;
});
```
