# Motion Authoring

create-motion is authored motion design: VideoCreator draws the visuals and
choreographs them in one seekable HyperFrames composition. There is no
template, scene recipe or style menu. The storyboard is the approval unit;
the source is task-local craft inside it.

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
| 1 | 0.0 | 0.8 | Title builds word by word | "Learn New Language" | per-word blur-in, lime glow | sparse intro plucks |
| 2 | 0.8 | 1.6 | ... | ... | zoom-through into beat 3 | drop at 1.6 |

## Design
Palette (hex), type (family/weight/sizes, local fonts), surfaces, depth,
light; what is drawn in SVG/CSS vs supplied.

## Motion language
Easing family, seam types between beats, camera logic, holds, stagger rules.

## Audio plan
Tempo, key/energy curve, drops and hit times (seconds), SFX list with times.
Precise enough for audio-creator to produce a matching finished WAV.

## Pending
One line per pending id: what it is, which producer, the exact spec.
```

`motion.py propose` checks: front matter keys and values, beats rows with
numeric `start`/`end` that are contiguous from 0 to `duration` (±0.05s),
and that `pending` ids are listed under `## Pending`. It never judges taste.

## Source Contract

- One `index.html` whose root element is
  `<div id="root" data-composition-id="motion" data-start="0"
  data-width="<w>" data-height="<h>" data-duration="<duration>" data-fps="30">`
  with an opaque background. Sub-compositions are allowed only as local files
  referenced from it.
- Copy `gsap.min.js`, `GSAP-LICENSE.txt`, `gsap-provenance.json` from
  `../tour/assets/` into `source/assets/`. Everything else is local under
  `source/assets/`: drawn SVG, supplied or dependency-delivered images,
  local fonts (`@font-face` with a local file or `local(...)`), finished WAVs.
  No `http(s)://` URL anywhere in the source; the helper rejects it.
- One paused timeline, built synchronously:
  `const tl = gsap.timeline({paused: true}); ...;
  window.__timelines ||= {}; window.__timelines["motion"] = tl;`.
  No autoplay, clocks, timers, `Math.random` without a fixed seed, remote
  requests, hover/scroll triggers or runtime DOM creation after load.
- Audio: each finished WAV is one `<audio id=… src="assets/…"
  data-start data-duration [data-track-index]>` at unity volume; more than
  one WAV needs a distinct positive `data-track-index` each. HyperFrames owns
  playback; JS never touches media elements. No loudness correction here: a
  clipping result goes back to audio-creator.
- On-screen copy renders verbatim from the approved storyboard.

## Craft notes

- Build the hero frame of every beat as a static state first; judge it at
  native size, then animate between states.
- Seams carry the film: prefer motion-matched handoffs (zoom-through,
  match-move, morph, rack focus) over cuts, and keep the direction of travel
  consistent across a seam.
- Type is the main actor in most launch pieces: per-word/letter staging,
  tracking and weight changes, blur-in, masks. Hold every line long enough to
  read (roughly 0.3s + 0.06s per character minimum).
- Counters, bars and UI states need in-between frames (eased value tweens),
  never jumps.
- Draw real-feeling UI: rounded geometry, consistent radii and shadows, real
  label text, believable data. Simplified stand-ins are fine and are named in
  the Report.
- Put audio hits on the storyboard times; if the delivered WAV's beats differ,
  move the visual hits to the measured audio, not the reverse.

## Render

```sh
python3 ${HERMES_SKILL_DIR}/scripts/motion.py render --approved-plan <storyboard.md> \
  --approval-sha256 <hash> --source <source> --out <new dir> --quality draft|final [--inputs <json>]
```

Verifies the storyboard hash and front matter, the root attributes, no remote
URLs, runs `hyperframes lint` (strict on final), renders with the installed
`hyperframes` CLI, probes the MP4 (canvas, 30fps, duration ±0.1s, audio
presence), measures loudness/true peak, writes a contact sheet and
`render.json` with a source tree hash. `final` additionally requires every
pending id resolved in `--inputs` to a file under the source, audio present
unless the storyboard says `audio: none`, and true peak < 0 dBTP.
Outputs go to a new directory; nothing is overwritten.
