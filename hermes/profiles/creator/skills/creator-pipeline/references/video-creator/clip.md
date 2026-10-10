# video-creator: clip

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-clip` — one short, silent, single-shot video generated from a subject and a motion direction, optionally animating a supplied image.
- `edit-clip` — trims, fits, mutes or re-encodes one existing segment (MP4, WebM, GIF) without redrawing it.
- `analyze-clip` — technical and visual findings with timestamps on one existing short video; no new video.

## Range

- Generated: 1–15 s (default 5), silent, 720p request; aspects 16:9 (default), 9:16, 1:1, 4:3, 3:4, 3:2, 2:3. One visible action and one camera instruction, not a multi-scene storyboard.
- Looks: cinematic, flat-animation, anime-2d (TV-style cel, simple backgrounds), painted-anime (cel characters on lush painted backgrounds), picture-book, clay, pixel (an aesthetic, not grid-correct sprite animation), or a described one.
- A starting still (`source`) or one appearance image (`reference`) can steer it; either needs consent for the upload.
- Not expressible: narration, montage, exact lip-sync, a deterministic animation of a logo, seamless loops.
- Edit and analyze work on sources of at most 60 s; edit changes length, format, framing and sound, not the picture.

## Where directions go

- `style` carries the look; one file per option under `references/styles/` of `generate-clip`, e.g. `skill_view(name="generate-clip", file_path="references/styles/clay.md")`.
- `what_for` carries subject, setting and use; `motion` carries the action and camera; `aspect`, `duration`, `source`, `reference`, `note` carry the rest.

## Boundaries

- Several shots, a story or a music piece: [music-video](music-video.md) for a generated one, [story](story.md) for approved characters, [promotion](promotion.md) for drawn motion.
- Text, logo or UI on screen is typeset in an authored piece ([ad](ad.md), [promotion](promotion.md)); a generated clip is text-free and can serve as a shot there.
- Joining finished parts under a soundtrack: [master](master.md).

## Examples

No stored example; propose the leaf's representative sample unit: one short single-shot draft (about 5 s) with a poster frame, in one named style.
