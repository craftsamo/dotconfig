# video-creator: music-video

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-music-video` — a short model-generated music video (MV) from a lead subject, a world and a rendering medium; a numbered proposal comes first, then the video.

## Range

- 5–15 s (default 15, or 10 when a reference is used); aspects 16:9 (default), 9:16, 1:1, 4:3, 3:4, 3:2, 2:3.
- Worlds (`theme`): theater, night-city, dream-garden, graphic-space, or a described one; `theme_detail` overrides motifs, palette, material, light.
- Rendering (`style`): anime-3d, anime-2d, painted-anime, stark-graphic (two or three flat colours, geometric planes, colour cards), picture-book, live-action, mixed-media, or a described one.
- Staging (`direction`): performance (default), typographic, montage, opening; mixes allowed. Rhythm (`pace`): relaxed, steady, snappy, intense. Shot boundary (`transition`): continuous, cut, match-cut, whip, dissolve.
- Sound (`music_mode`): generated, supplied, silent. A supplied song is finished separately, with the video as a silent visual master.
- A reference video is only sampled locally for camera, pace, world or type. A character image (`character_reference`) preserves the lead's identity and needs consent for the upload.
- Not expressible: exact lyric, beat or lip sync, seamless loops, full songs; exact lettering needs a text-free base finished elsewhere.

## Where directions go

- One file per option under `references/themes/`, `styles/`, `direction/`, `pace/`, `transition/`, e.g. `skill_view(name="generate-music-video", file_path="references/direction/montage.md")`. `references/spatial-direction.md` covers reference-led spatial camera motion.
- `subject`, `theme`, `style`, `performance`, `direction`, `pace`, `transition`, `must_keep`, `words`, `note` carry the direction.

## Boundaries

- One shot, no music framing: [clip](clip.md). Authored (drawn) motion: [promotion](promotion.md). Characters from approved art acting a narrative: [story](story.md).
- The music itself: [music](../audio-creator/music.md). Joining picture and soundtrack: [master](master.md).

## Examples

No stored example; propose the leaf's representative sample unit: the numbered proposal, a short MV draft of one world and one performance.
