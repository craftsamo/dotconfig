# Commission — video-creator: story

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a short character story: recurring characters from their approved art act out a narrative across scenes with dialogue from an approved script, staged as 2.5D HTML animation | `create-story` | free, 10..120 seconds, 24/25/30/50/60fps (default 30), 9:16 default / 16:9 / 1:1 / 4:5; always kind="work"; storyboard + cast hashes first, approval releases drafts/final; script (Writer), missing poses (image-creator mascot revise), voices/music (audio-creator speech + mix) are separate units; no lip sync, no generated characters |

## Choosing and filling

`create-story` is the served route for a short character story (10..120 s):
recurring characters from their approved art act out a narrative across
scenes, with dialogue from an approved script and a finished soundtrack,
staged by VideoCreator as 2.5D HTML animation. It is not a learning
explanation with a character ([explainer-video](explainer-video.md)), a
piece that presents a product or place ([promotion](promotion.md)), a
model-generated MV ([music-video](music-video.md)) or a generated shot
([clip](clip.md)). Characters are never generated per scene: generated
video drifts from the approved art.

Settle with the user: premise (setup, turn, ending), purpose and viewer,
aspect and length (fps only if the user asks: 24/25/30/50/60, default
30), the cast, the world and its look. The cast means
approved art that already exists — a mascot anchor and its pose pack, or
supplied character images. An unspecified cast is not "no cast": ask whether
it means existing characters or new ones. New characters and missing poses are
image-creator mascot units (a new design, or a round-B `pack: custom` of
the missing poses on the approved anchor) before or alongside the
storyboard. Tell the user up
front there is no lip sync: speaking is staged with poses, expressions and
timing.

Plan the dependency order as separate units: script through Writer's
write-script (every spoken and on-screen line), cast art through
image-creator, then the storyboard approval, then voices through
audio-creator's generate-speech per line and create-mix for lines, music
and SFX on the storyboard's timeline (captions come with the Mix when the
speech has word timing). A pending storyboard is a useful preliminary plan;
dependencies can be released once it names what they need.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-story` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; storyboard, drafts and final are not one-reply work |

## Round-trip and approvals

Keep every round in one work conversation. `cast` is a comma list of
`id=path` pairs pointing at approved art (one image or a pose directory
per character); `script` is the approved Writer script file. Round A
returns `proposal-v<N>/storyboard.md`, its SHA-256, the cast hashes, a status
and a pending list. Show the user the storyboard (beats, cast on screen, quoted
lines, world, audio plan); never approve on their behalf.
After approval send `approved_plan` + `approval_sha256` in the same
conversation.

For each pending id, release its producer as its own unit and return the
finished file into the same video conversation:

- `script`: Writer's write-script; a changed line means a new storyboard.
- `cast:<id>-<pose>`: image-creator `generate-mascot` round B for the
  missing poses only: `intent: revise <that character's round-A dir>`,
  `anchor: <approved concept>`, `pack: custom`, `items: <missing poses>`
  (at least two items; batch the missing poses of one character). A
  character that did not come from a mascot job is a new generate-mascot
  job with the supplied image as `reference`, approved like any concept.
  Pass the new pack directory: only items its manifest marks passed count.
- `audio`: audio-creator — generate-speech for each line from the
  approved script, then create-mix placing lines, music and SFX on the
  storyboard's audio plan into one master of the exact duration. Pass the
  master (and the Mix `captions.json` when captions are drawn) back.

Changed beats, lines, cast, duration or aspect need a new numbered
storyboard and approval; redrawing a place or restaging a shot does not.
