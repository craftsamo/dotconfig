# Build — video-creator: story

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-story` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; storyboard, drafts and final are not one-reply work |

## Supervising

Keep every round in one work conversation. `cast` is a comma list of
`id=path` pairs pointing at approved art (one image or a pose directory
per character); `script` is the approved Writer script file. Round A
returns `proposal-vN/storyboard.md`, its SHA-256, the cast hashes, a status
and a pending list. Relay the storyboard (beats, cast on screen, quoted
lines, world, audio plan) to the client; never approve on their behalf.
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
