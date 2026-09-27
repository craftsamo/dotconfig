# Promotion Authoring

create-promotion is authored motion design: VideoCreator draws the visuals
and choreographs them in one seekable HyperFrames composition. There is no
template, scene recipe or style menu. The storyboard approves the structure;
the look is iterated against the reference and the leaf's Standard.

| `aspect` | dims |
| --- | --- |
| `16:9` | 1920x1080 (default) |
| `9:16` | 1080x1920 |
| `1:1` | 1080x1080 |
| `4:5` | 1080x1350 |

Always 30fps, 3..60 seconds. A ratio change is a new storyboard, never a
crop or scale of an approved layout.

## Storyboard (`storyboard.md`)

VideoCreator writes it; the client approves its exact bytes through Creator.
It is a structure contract. Write the look in words and reference points,
never in pixels: a storyboard that says "counter 220px" freezes a size the
first draft may show is wrong. (2026-09-23: a storyboard with numeric sizes
kept the same three "too small, too flat" gaps from the first review to the
final render, and the film scored lowest of three blind candidates.)

```markdown
---
aspect: 16:9
duration: 16
fps: 30
audio: pending        # none | supplied | pending
pending: audio        # comma-separated ids, or empty
---

# <title>

## Intent
One paragraph: what the viewer should feel and remember, and (reproduce)
which reference qualities are being matched.

## Beats
| # | start | end | scene | on-screen copy | motion / transition | audio |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0 | 0.8 | Title builds word by word, hero-sized | "Learn New Language" | per-word blur-in, lime glow | sparse intro plucks |
| 2 | 0.8 | 1.6 | ... | ... | zoom-through into beat 3 | drop at 1.6 |

## Look
Palette (hex is fine), type family and feel (weight, rounded/geometric,
local font stand-ins), surfaces, depth and light, density — described
relative to the frame and the reference ("the counter dominates the frame",
"cards tilt in 3D like the reference"), never as coordinates.

## Motion language
Easing family, seam types between beats, camera logic, holds, stagger rules.

## Audio plan
Tempo, key/energy curve, drops and hit times (seconds), SFX list with times.
Precise enough for audio-creator to produce a matching finished WAV.

## Pending
One line per pending id: what it is, which producer, the exact spec.
```

`promotion.py propose` checks: front matter keys and values, beats rows with
numeric `start`/`end` that are contiguous from 0 to `duration` (±0.05s),
and that `pending` ids are listed under `## Pending`. It never judges taste.

## Source Contract

- One `index.html` whose root element is
  `<div id="root" data-composition-id="promotion" data-start="0"
  data-width="<w>" data-height="<h>" data-duration="<duration>" data-fps="30">`
  with an opaque background. Sub-compositions are allowed only as local files
  referenced from it.
- Copy `gsap.min.js`, `GSAP-LICENSE.txt`, `gsap-provenance.json` from
  `../tour/assets/` into `source/assets/`. Everything else is local under
  `source/assets/`: drawn SVG, supplied or dependency-delivered images,
  local fonts (`@font-face` with a local file or `local(...)`), finished WAVs,
  supplied footage as given (a segment that needs trimming or fitting is an
  edit-clip dependency first, never re-encoded inside the source).
  No `http(s)://` URL anywhere in the source; the helper rejects it.
- One paused timeline, built synchronously:
  `const tl = gsap.timeline({paused: true}); ...;
  window.__timelines ||= {}; window.__timelines["promotion"] = tl;`.
  No autoplay, clocks, timers, `Math.random` without a fixed seed, remote
  requests, hover/scroll triggers or runtime DOM creation after load.
- Audio: each finished WAV is one `<audio id=… src="assets/…"
  data-start data-duration [data-track-index]>` at unity volume; more than
  one WAV needs a distinct positive `data-track-index` each. HyperFrames owns
  playback; JS never touches media elements. No loudness correction here: a
  clipping result goes back to audio-creator.
- On-screen copy renders verbatim from the approved storyboard.

## Craft

- Build the hero frame of every beat as a static state first and judge it
  at native size against the reference frame at the same time. Only then
  animate between states.
- Size by the frame, not by habit: measure the reference's hero element as
  a share of the frame width/height and match it. When in doubt, go bigger
  and bolder; launch films read on a phone.
- Depth is built, not implied: CSS 3D (`perspective`, `rotateX/Y`,
  `translateZ`), stacked shadows, blur for focus and speed, parallax layers
  moving at different rates.
- Draw the density the reference has: illustrated characters, props, UI with
  real-looking labels and data, particles. Build reusable SVG symbols so
  detail is cheap to repeat.
- Seams carry the film: prefer motion-matched handoffs (zoom-through,
  match-move, morph, rack focus) over cuts, and keep the direction of travel
  consistent across a seam.
- Type is the main actor in most launch pieces: per-word/letter staging,
  weight and tracking changes, blur-in, masks. Hold every line long enough to
  read (roughly 0.3s + 0.06s per character minimum).
- Counters, bars and UI states need in-between frames (eased value tweens),
  never jumps.
- Put audio hits on the storyboard times; if the delivered WAV's beats
  differ, move the visual hits to the measured audio, not the reverse.
- Name simplified stand-ins in the Report; do not present them as the
  reference's real assets.

## Showcase and series

A PV or showcase reel introduces one subject (a store, site, product,
event) through its own supplied material. Its content decides the middle
of the film; the motion carries it.

- Footage is one `<video id=… class="clip" src="assets/…" muted playsinline
  data-start data-duration data-media-start>` per range; HyperFrames owns
  playback, JS never touches it, and its sound, if kept, is a separate
  timed `<audio>` with the same timing. Stills move by an animated wrapper
  (camera push, pan, parallax), never by editing the image.
- A page capture slid or scrolled as a still keeps its viewport-fixed UI
  (header, floating buttons) on a separate stationary layer, or the fixed
  UI moves and duplicates. Say "edited motion" in the Report, never
  "native scrolling".
- Lay out for this subject's real item count and name lengths. More items
  get more time or a sequence, not smaller type; if they cannot all fit
  the approved duration readably, the storyboard says which ones appear.
- Series (`series_of`): read the earlier episode's approved
  `storyboard.md` and final `sheet.png`. The new storyboard keeps what
  makes it the same series (look, type, audio identity, brand ending) and
  gives this subject its own opening from its own material in the first
  frame and its own middle scenes. An earlier episode's intro is not
  carried over by default; episodes that open the same way read as the
  same video. Start the source from a copy of that episode's source in a
  new directory; the earlier episode is never edited. Every episode is
  its own storyboard approval.

## Render

```sh
python3 ${HERMES_SKILL_DIR}/scripts/promotion.py render --approved-plan <storyboard.md> \
  --approval-sha256 <hash> --source <source> --out <new dir> --quality draft|final \
  [--reference <reference video>] [--inputs <json>]
```

Verifies the storyboard hash and front matter, the root canvas/duration, no
remote URLs, runs `hyperframes lint` (strict on final), renders with the
installed `hyperframes` CLI, probes the MP4 (canvas, 30fps, duration ±0.1s,
audio presence), measures loudness/true peak, writes `sheet.png` and
`render.json` with a source tree hash. With `--reference` it also writes
`compare.png`: reference frames above, draft frames below, at the same eight
relative positions of each film (a reference of another length still fills
its row). `final` additionally requires every pending id resolved in
`--inputs` to a file under the source, audio present unless the storyboard
says `audio: none`, and true peak < 0 dBTP. Outputs go to a new directory;
nothing is overwritten.
