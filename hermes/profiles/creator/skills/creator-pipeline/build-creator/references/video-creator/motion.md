# Build — video-creator: motion

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-motion` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; storyboard, authoring/drafts and final render are not one-reply work |

## Supervising

Keep every round in one specialist work conversation. Round A returns
`proposal-vN/storyboard.md`, its SHA-256, a status and a pending list. Relay
the storyboard itself (beats, copy, design, motion language, audio plan) to
the client for approval; never approve on the client's behalf and never
recompute a hash for changed bytes. After approval send `approved_plan` +
`approval_sha256` in the same conversation: that releases authoring, draft
renders and — once pending items are resolved — the final render.

For each pending id, release its producer as its own unit and return the
finished file into the same video conversation:

- `audio`: brief audio-creator from the storyboard's `## Audio plan`
  (tempo, energy curve, drop and hit times in seconds, SFX list with times,
  exact duration). Usual path: generate-music or create-music for the bed,
  create-sfx/generate-sfx for hits, then create-mix to place them on the
  storyboard's timeline and return one master WAV. Hand VideoCreator the
  master path; it places it and resolves `audio` in its inputs file.
- `image:<name>`: the fitting image-creator leaf with the storyboard's exact
  spec (subject, size, background/alpha, style). Never ask VideoCreator to
  generate it.

Small execution fixes after a draft (spacing, easing, legibility, a missed
hit) stay inside the approved storyboard. Changed beats, copy, duration,
aspect or look need a new numbered storyboard and a new approval.
