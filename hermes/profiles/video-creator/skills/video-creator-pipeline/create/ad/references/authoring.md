# Ad Authoring

Author HTML/CSS/GSAP for this task, not a generic ad-template DSL. There is
no fixed layout: theme/style/direction are concrete recipes to adapt, not a
scene graph to instantiate. Output canvas is one of four fixed ratios, always
30fps:

| `aspect` | dims        |
| -------- | ----------- |
| `9:16`   | 1080x1920 (default when `aspect` is absent) |
| `16:9`   | 1920x1080   |
| `1:1`    | 1080x1080   |
| `4:5`    | 1080x1350   |

No arbitrary size is accepted, and a layout authored for one ratio is never
cropped or scaled into another — a ratio change is new authored source, plan
and approvals, not a transform.

## Plan Contract (`plan.json`)

VideoCreator writes `plan.json`, NOT the client, but it may only contain
client-approved product facts, exact copy and exact claims — nothing invented:

```json
{
  "version": 1,
  "product": "Acme Focus Timer",
  "audience": "Remote workers who lose track of time",
  "message": "Stay focused without burning out",
  "cta": "Try Acme Focus Timer free",
  "theme": "office",
  "style": "bold-graphic",
  "direction": "claim-led",
  "theme_detail": "Warm wood desk, soft daylight through a window",
  "claims": "<verbatim, client-supplied evidence and any stated restrictions; never invented, never 'verified' or 'No.1' without that exact supplied backing>",
  "note": "",
  "duration": 15,
  "aspect": "9:16",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "assets": {
    "assets/gsap.min.js": "<sha256>",
    "assets/GSAP-LICENSE.txt": "<sha256>",
    "assets/gsap-provenance.json": "<sha256>",
    "assets/logo.png": "<sha256>"
  },
  "copy": [
    {"id": "message", "text": "Stay focused without burning out", "role": "message", "start": 1, "end": 6},
    {"id": "claim", "text": "<exact backed claim text>*", "role": "claim", "start": 6, "end": 10},
    {"id": "cta", "text": "Try Acme Focus Timer free", "role": "cta", "start": 10, "end": 15}
  ],
  "samples": [
    {"at": 0, "expect": "Opening product shot"},
    {"at": 3, "expect": "Message readable"},
    {"at": 8, "expect": "Claim readable with its footnote marker"},
    {"at": 12, "expect": "CTA readable"},
    {"at": 14.966666666666667, "expect": "Final visible frame retains the CTA"}
  ]
}
```

Illustrative values only. The maintainer's test suite includes an explicitly
fictional TEST FIXTURE, never a real or client-approved ad.

- `version` must be `1`. `fps` must be exactly `30`. `aspect` is optional and,
  when present, must be exactly one of `9:16`, `16:9`, `1:1`, `4:5` (a bool,
  list, dict or unlisted string is rejected). `width`/`height` must exactly
  match that ratio's fixed dims (`9:16`=1080x1920, `16:9`=1920x1080,
  `1:1`=1080x1080, `4:5`=1080x1350). Omitting `aspect` validates only against
  the original `9:16` 1080x1920 dims — it is never inserted into the plan a
  helper call returns or writes; an existing frozen plan/preview authored
  without `aspect` is unaffected.
- `duration` is `6..30` seconds.
- `theme`/`style`/`direction` accept the listed option or an equally concrete
  free-text description (`other: true`); a custom value is saved and
  implemented verbatim, never coerced onto the nearest listed option.
- `assets` is the COMPLETE approved map of every file under `assets/` in the
  source directory (relative path -> SHA-256), including the vendored GSAP
  files, fonts, and any supplied audio/video/logo. `freeze` rejects a source
  whose actual `assets/` contents differ from this map in either direction.
   It is never `{}`: `gsap.min.js`, `GSAP-LICENSE.txt` and
   `gsap-provenance.json` in the source assets directory are always required (the runtime itself),
  so a text-only ad's map still has exactly those three entries.
- At most **one** audio track (one `.wav`) is supported in this version.
  Every `.wav` this map declares must be placed by exactly one `<audio>`
  element in `index.html` — an asset present in `assets/` but never placed
  ("surprise audio") is rejected, as is more than one placed track. `.mp4`
  assets are probed with `ffprobe` directly (sides <=4096px, area
  <=9,000,000px, exactly one video stream with a reported codec, source
  duration covering its placement); `.png`/`.jpg`/`.webp` assets are decoded
  with the same static-PNG/JPEG/WebP-only, dimension-bounded `image()` check
  used elsewhere in this hands — a renamed non-image, an animated image or an
  oversized image is rejected before the project is ever frozen, not left for
  a later render to discover. Every `<audio>`/`<video>` element needs a
  unique `id` and only these attributes: `id class src muted playsinline
  data-start data-duration data-media-start data-track-index style preload
  data-volume` — no `autoplay`/`loop`/other retiming attribute, and
  `data-media-start` must be absent or `0` (HyperFrames owns any actual
  in-source trim). No JS may read/set `.volume`/`.muted` or a `volume:`
  tween target; audio finishing beyond unity-volume playback is a separately
  approved step, not something this leaf's JS does silently.
- `copy` rows: `id` (lowercase slug, unique), `text` (exact plain string,
  1..2000 chars), `role` (`message|claim|cta|support`), `start`/`end`
  (seconds within `0..duration`, `end > start`). At least one `message` row's
  `text` must equal the plan's top-level `message` exactly, and at least one
  `cta` row's `text` must equal the plan's top-level `cta` exactly — this is
  the authoritative binding between the client-approved fields and the
  on-screen copy. Any `claim`-role row requires a nonempty top-level `claims`
  field (evidence/restrictions); the helper checks presence, never truth. Every
  `cta`-role row must hold for at least 2 seconds (`end - start >= 2`).
- `samples`: `3..40` ordered, unique `at` times with a short `expect` string
  each. Must start at `0` and end at or after `duration - 1/30` (the last
  representable frame; a sample can never land exactly at `duration` itself,
  since no frame exists there). Every copy row needs at least one sample
  strictly inside its `start..end` hold, so each declared line has actual
  proof evidence, not just structural timing.

## Source Contract

- One standalone `index.html` with `#root`:
  `data-composition-id="ad" data-start="0" data-width="<plan width>"
  data-height="<plan height>" data-duration="<duration>" data-fps="30"`,
  matching the approved plan's ratio (its CSS-sized canvas is the same
  variable dims, not a fixed 1080x1920). No template wrapper; root background
  is opaque.
- Copy `gsap.min.js`, `GSAP-LICENSE.txt` and
  `gsap-provenance.json` from this hands' sibling
  `../tour/assets/` (the existing vendored GSAP; do not re-vendor or modify
  it) into the ad source's `assets/`. Every other asset stays local under
  `assets/`; PNG/JPG/WebP only for logos/images this version (no SVG — ask the
  client for a raster export). Local fonts or supplied WOFF2 only; declare
  named installed OS fonts with `@font-face { src: local(...) }`.
- One element per copy row, its `id` matching the plan row's `id`, containing
  exactly that row's text as rendered plain text (nested `<span>`s for staged
  reveal are fine; the checker only whitespace-normalizes them, never
  rewrites). Every other visible text outside `<script>/<style>/<title>` must
  also live inside a declared copy id's element — the freeze/check helper
  rejects any leftover visible text as a silent, undeclared addition.
- Build synchronously: `const tl = gsap.timeline({paused:true});`, explicit
  time-positioned tweens, then
  `window.__timelines ||= {}; window.__timelines["ad"] = tl;`. No autoplay,
  clocks, timers, randomness, external requests, hover/scroll triggers or
  runtime DOM creation. Prebuild every state; seek it via timeline.
- Any supplied audio is an already-finished, standalone PCM WAV (never
  synthesized here): place it with an id-bearing `<audio>` at unity volume
  (no `muted`, no `data-volume` other than `1`) and explicit
  `data-start`/`data-duration` that the file's own duration covers. Any
  supplied video-in-video is muted (`muted` attribute) with the same explicit
  timing; HyperFrames owns playback — never call `.play()`/`.pause()`/set
  `.currentTime`/`.playbackRate` from JS.

## Freeze / Snapshot / Render

System `python3` on this host has no Pillow; every invocation goes through
`uv run --no-project --with Pillow python` (matches the existing `analyze/ad`
and `creator-pixel-art` leaves' documented convention):

```sh
uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-render.py freeze \
  --source <absolute-source-dir> --plan <deliver>/plan.json \
  --approval-sha256 <sha256-of-plan.json> --project <deliver>/ad-project

uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-render.py snapshot \
  --project <deliver>/ad-project --out <deliver>/ad-preview
# prints preview_sha256; that folder + hash are what the client approves next

uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-render.py render \
  --project <deliver>/ad-project --approved-preview <deliver>/ad-preview \
  --approval-sha256 <sha256-of-preview.json> --out <deliver>/ad-final
```

`freeze` binds the exact approved `plan.json` bytes (its own SHA-256, checked
against `--approval-sha256`) to a source/asset inventory it validates and
copies into a fresh, exclusive `--project` directory outside the source tree;
it re-verifies the source directory is byte-identical before and after the
copy. `snapshot` re-validates the frozen project (integrity, markup, copy
ledger), runs `hyperframes check` (contrast must be enabled and nonzero) and
`snapshot` at every sample time, and binds project integrity + frame hashes +
check hash into `preview.json`, whose own SHA-256 is the value the client
approves. `render` requires both `--approved-preview` and its exact
`--approval-sha256` — no bypass — re-validates every bound frame/check hash,
re-runs `hyperframes check`, renders strictly at 30fps with one worker, fully
decodes the output with `ffmpeg`, and checks codec/pixel-format/dimensions/
duration/fps/audio-presence-vs-plan with `ffprobe` before writing `qa.json`
with `semantic_review: pending`, `temporal_review: sampled only`,
`audio_listening: unverified` and `media_generation: 0`. None of these helper
checks are a visual or listening pass; only a human review against decoded
frames earns that. All outputs must be fresh directories, never nested inside
source/project/preview. Paths are absolute, physical and symlink-free.

## Compatibility

This leaf is standalone: composition id `ad`, not `tour`. It shares no
project format with `create-tour`'s v1/v2/v3 projects and does not read or
write them. It reuses only `tour.py`'s/`authored.py`'s low-level file, hash,
image and HyperFrames-CLI primitives through an explicit path import — never
their scaffold/freeze/render dispatch, and never edits either file.

## Runtime Identity

The preview records the resolved HyperFrames executable and its version.
Render rejects a different executable/version: make a new preview and get
approval, never upgrade frozen input or approve a newly computed hash yourself.
The existing tour CLI runner is reused without modification; no package
installation happens in this leaf. This guards reported CLI drift, not all
browser/OS/font differences. Supplied WOFF2 fonts are hash-bound assets;
installed system fonts remain an explicitly disclosed environment dependency.
