# video-creator: story

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-story` — an authored character story video: recurring characters from their approved art act out a short narrative across scenes, staged as 2.5D animation in HTML/CSS/SVG/GSAP; storyboard and cast come first.

## Range

- 10–120 s (default 60); aspects 9:16 (default), 16:9, 1:1, 4:5; 24–60 fps (default 30).
- The cast is approved art that already exists (a mascot anchor and its poses, or supplied character images); characters are never generated per scene. Speaking is staged with poses, expressions and timing; no lip sync.
- Dialogue comes from an approved script, sound from a finished WAV or Mix master; pending lines or inputs stay pending.
- Rendering (`style`): picture-book, cartoon, anime-2d, paper-cut, sumi-ink, watercolor, crayon, silhouette, or a described one that suits the cast art. The style renders the world only; for an anime story the cast itself must already be anime-style art, such as a mascot `anime-2d` anchor and poses. `world` carries setting, era, places, mood; supplied backgrounds, props and footage inserts can be added.
- Not expressible: learning explainers, product or place presentations, generated MVs or clips, new character design, speech or music synthesis.

## Where directions go

- Authored video: the producer writes the storyboard. The direction travels in `note` (plus `premise`, `world`, `style`, `what_for`) with named techniques from video-creator's `references/motion-vocabulary.md`: `skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary.md")`.
- Option vocabulary: one file per option under `references/styles/` of `create-story`, e.g. `skill_view(name="create-story", file_path="references/styles/watercolor.md")`.

## Boundaries

- Teaching a topic: [explainer-video](explainer-video.md). Presenting a product or place: [promotion](promotion.md). A generated MV: [music-video](music-video.md). A generated shot: [clip](clip.md).
- Cast art and missing poses: [mascot](../image-creator/mascot.md). Voices and soundtrack: [speech](../audio-creator/speech.md), [mix](../audio-creator/mix.md).

## Examples

No stored example; propose the leaf's representative sample unit: a short storyboard-approved draft of one scene of the story on the existing cast.
