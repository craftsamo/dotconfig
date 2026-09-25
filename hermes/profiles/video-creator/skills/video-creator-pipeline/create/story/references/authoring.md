# Story Authoring

create-story stages a short narrative with recurring characters in one
seekable HyperFrames composition. The characters are the client's approved
art; the world, camera, acting and seams are yours. There is no template or
scene recipe.

| `aspect` | dims |
| --- | --- |
| `9:16` | 1080x1920 (default) |
| `16:9` | 1920x1080 |
| `1:1` | 1080x1080 |
| `4:5` | 1080x1350 |

Always 30fps, 10..120 seconds. A ratio change is a new storyboard.

## Storyboard (`storyboard.md`)

The same front matter and structure rules as create-promotion's storyboard
(`aspect`, `duration`, `fps: 30`, `audio: none|supplied|pending`,
`pending`; contiguous `## Beats` from 0 to `duration`; `## Pending`), plus a
cast and dialogue:

```markdown
---
aspect: 9:16
duration: 45
fps: 30
audio: pending
pending: audio, script, cast:mika-wave
---

# <title>

## Intent
What the viewer should feel; the setup, turn and ending in one paragraph.

## Cast
| id | who | art on hand | needed |
| --- | --- | --- | --- |
| mika | the curious lead | front, side, happy, surprised | wave (pending cast:mika-wave) |
| tobi | her calm friend | front, thinking | - |

## Beats
| # | start | end | scene | cast | dialogue | camera / acting / transition | audio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 4 | rooftop at dusk, wide | mika | - | pull-back reveal; mika small against the sky | wind, music in |
| 2 | 4 | 9 | same, two-shot | mika, tobi | mika: 「今日で最後なんだね」 | push-in; mika turns side->front on the line | line 1 |

## World and look
Places, palette, light, materials, how the world matches the cast's line
and shading; described in words, never pixel sizes.

## Audio plan
Every line with its speaker and time, music energy curve, SFX with times,
exact duration: precise enough for audio-creator's Mix.

## Pending
One line per pending id: what it is, which producer, the exact spec.
```

Every spoken line in the dialogue column is `speaker: 「line」` (or `"line"`),
the speaker on screen in that beat (or `vo`/`narrator`), the line verbatim
from the approved script; no `|` inside a cell. A cast pose that does not
exist yet is a pending `cast:<id>-<pose>`. `aspect` is always written out.
`propose` appends a `## Cast art (bound by propose)` block with the hash of
every cast image and the script; never write or edit that block by hand.

## Source Contract

The create-promotion source contract applies, with root
`data-composition-id="story"`: one `index.html`, local assets only, vendored
GSAP copied from `../tour/assets/`, one paused timeline registered as
`window.__timelines["story"]`, no clocks, timers, unseeded randomness or
remote requests, finished WAVs as timed `<audio>` elements HyperFrames plays.

- Cast art is copied byte for byte into `source/assets/cast/<id>/` and
  referenced by its path from the source; the render checks every cast
  member appears that way from its bound bytes. A mascot pack directory
  counts only the items its `manifest.json` marks passed. Never
  recolour, crop into a new drawing or trace it; scale, flip, position,
  layer order, shadow and CSS transforms are fine.
- Footage inserts (supplied or generate-clip shots) follow create-promotion's
  "Showcase and series" footage markup and never show a cast member: a
  generated character drifts from the approved art.
- Mix captions, when drawn, are one timed element per sidecar entry:
  `id="mix-caption-<N>" class="clip" data-start data-duration` with the
  sidecar text verbatim; the render checks them with `--captions`, and
  without a sidecar no `mix-caption-*` element may exist.

## Acting

Characters perform with what the art allows, never with invented drawings:

- Pose and expression swaps on the beat of the line or reaction, with a
  short anticipation (a small dip or lean) before the swap.
- Body motion from transforms: a breathing scale of 1-2 %, a lean, a hop
  with squash on landing, a turn by swapping side and front art mid-move.
- The speaker is clear: framing favours them, the listener dims or softens
  slightly, a small bounce or lean lands on the stressed word.
- No lip sync. A talking character is staged with pose, expression and
  body timing on the line; never call that lip sync, and never animate a
  mouth that the art does not provide as separate approved images.
- Hold reaction shots; a story needs a beat of stillness before the turn.

## Scenes and camera

- Build each place once as layered planes (far, mid, near) so the camera
  can push, truck and parallax; reuse the same place for continuity.
- Keep screen direction: a character exiting right enters the next scene
  from the left; a match cut or carrier handoff joins places.
- Time of day and weather carry mood; change them only where the
  storyboard says.

## Render

```sh
python3 ${HERMES_SKILL_DIR}/scripts/story.py render --approved-plan <proposal-vN/storyboard.md> \
  --approval-sha256 <hash> --source <source> --out <new dir> --quality draft|final \
  [--inputs <json>] [--captions <Mix captions.json>] [--reference <video>]
```

It runs create-promotion's render checks (hash, canvas, duration, lint,
render, probe, loudness, true peak, pending inputs) with `story.mp4`, plus
the cast-bytes and caption checks above.
