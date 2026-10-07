# video-creator: master

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-master` — one finished delivery master from already-approved parts: silent video segments joined in order, a finished soundtrack laid under them, optional burned-in captions plus an SRT sidecar.

## Range

- Join: `cut` (default) or `dissolve` of 0.1–2 s (default 0.5); segments share size and fps. A dissolve shortens the picture at each join, so the soundtrack must match the joined length.
- Soundtrack: a finished WAV of the exact total length or an audio-creator Mix bundle; absent means silent.
- Captions: an SRT or Mix captions, burned in at the bottom (default) or top, or attached as SRT only.
- It is deterministic and local and decides nothing creative: it does not trim, reframe, retime or recolour a part.
- Not expressible: overlays, logos or graphics on footage, keeping each segment's own sound, mixing or ducking, new motion or footage.

## Where directions go

- Nothing creative is carried: the form fields are `segments` (order), `transition`, `transition_seconds`, `audio` or `mix_bundle`, `captions`, `burn_captions`, `caption_position`, `note`.
- There is no option vocabulary and no storyboard; creative direction belongs to the parts: [clip](clip.md), [music-video](music-video.md), [promotion](promotion.md), [music](../audio-creator/music.md), [mix](../audio-creator/mix.md).

## Boundaries

- Changing one clip's length, ratio or sound: `edit-clip` in [clip](clip.md). Mixing audio: [mix](../audio-creator/mix.md).
- Motion graphics over footage: [promotion](promotion.md).

## Examples

No stored example; propose the leaf's representative sample unit: a join of two or three approved segments with one transition under a finished soundtrack, shown with join frames.
