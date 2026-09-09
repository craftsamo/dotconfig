# Character: Framing and Performance

`framing`, `performance` and `lip_sync` are three separate fields, not one
enum — a client's answer to "should there be a character?" almost always
needs unpacking into these three axes plus which assets are actually in
hand. This reference has no per-option file glob; read it whole.

## Framing: how much of the character is visible

- `none` — no character presence at all. This is a deliberate choice, not
  the default for "unspecified": Creator clarifies none vs. an existing
  character vs. a new one before this field is ever filled with `none`.
  With `none`, every other character field is forced empty (`performance:
  still`, `lip_sync: off`, no body/video/mouths/cues/sync) — there is
  nothing left to silently retain.
- `bust` — head-and-shoulders framing, typically alongside diagrams. This
  is the framing that most naturally supports mouth-cue lip sync, but it
  never proposes `lip_sync: cues` silently — an explicit `off` stays off,
  and cues are only compiled from actually-supplied, reviewed input (see
  Lip Sync below).
- `full` — full-body framing. Supports whatever `performance` was actually
  approved; a `full` framing is never automatically upgraded toward
  `animated` just because more of the body is visible.

## Performance: what kind of asset drives the character

- `still` — a single approved character image (`body`), held static or
  gently animated in CSS/GSAP (parallax, breathing loop, blink) by
  VideoCreator's own authored HTML. No supplied video.
- `puppet` — the same single-image asset contract as `still` (one `body`
  image, no `video`), but authored with more deliberate 2D-puppet-style
  motion (limb/head segments animated via CSS transforms on cropped image
  layers) rather than a passive idle loop. The schema does not distinguish
  `still` from `puppet` structurally — the difference is entirely in how
  the authored timeline moves the same still asset.
- `animated` — driven by an already-finished, already-synced muted MP4
  (`video`). No `body`, no `mouths`, no `cues` — a supplied video is either
  fully sufficient on its own (with `sync` proving hash-bound provenance
  for `lip_sync: baked`) or the performance stays `lip_sync: off`. This
  leaf authors no rig, no puppet skeleton and no talking-model inference
  for `animated` performance — the video is supplied as a finished asset.

## Lip Sync: how mouth movement is driven

- `off` — no speech-synchronized mouth movement is authored; an `animated`
  supplied video may already contain mouth motion, which is not certified as synced. Valid with
  any `performance`. Required whenever `audio.mode` is `none` (there is no
  narration to sync to).
- `cues` — only valid with `performance: still`/`puppet`. Requires an
  already-reviewed cue JSON (`cues`, see the Mouth Cue JSON section of
  [authoring](authoring.md)) and at least two `mouths` images including a
  `rest` shape; `propose`
  compiles those cues into a deterministic `mouth-track.js`, in the
  source's `assets/` directory, that swaps mouth image opacity on the
  timeline. This leaf never infers cue
  timing from text, ASR or raw audio — a missing cue file is a
  pending-inputs dependency, never a silently generated guess. `bust`
  framing is the natural home for this, but it is never proposed instead
  of an explicit `off`.
  No current hands leaf produces these reviewed cues automatically. If they
  are absent, Creator reports a capability gap until a separately approved
  cue-production method is available; neither the client nor AudioCreator
  is assumed to author cue JSON as part of an ordinary speech request.
- `baked` — only valid with `performance: animated`. Requires a `sync`
  receipt (see the Sync Receipt JSON section of [authoring](authoring.md))
  binding the supplied video's hash to the narration master's hash. This
  binds bytes only; it is not evidence the video's mouth movement actually
  matches the words, and this leaf performs no viseme/phoneme analysis to
  check it.

## Valid combinations at a glance

| `framing` | `performance` | `lip_sync` | Requires |
| --- | --- | --- | --- |
| `none` | `still` | `off` | nothing (no character assets at all) |
| `bust`/`full` | `still`/`puppet` | `off` | `body` |
| `bust`/`full` | `still`/`puppet` | `cues` | `body`, `cues`, `mouths` (>=2, incl. `rest`) |
| `bust`/`full` | `animated` | `off` | `video` |
| `bust`/`full` | `animated` | `baked` | `video`, `sync` |

Every other combination (e.g. `animated` + `cues`, `still` + `baked`, any
non-`none`/`still`/`off` triple under `framing: none`) is rejected by
`propose`/`freeze` before any source is authored. An existing character
missing a needed pose for the approved framing/performance is a
missing-only generation request through image-creator's mascot leaf that
preserves its approved identity — never a silently invented new character
or a silent downgrade of framing/performance/lip_sync to whatever assets
happen to be on hand.
