# video-creator: explainer-video

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-explainer-video` — an explanation of a topic toward a learning goal from approved words and supplied media, with no character, a bust presenter or a full-body presenter; a proposal comes first.

## Range

- Duration up to 180 s; 16:9 (1280x720) or 9:16 (720x1280); HyperFrames at 24–60 fps, or Motion Canvas at 30 fps.
- The engine is chosen explicitly in the proposal: HyperFrames suits HTML, UI or media compositions; Motion Canvas suits reactive diagrams, algorithms and Canvas-based explanation.
- `framing` (none, bust, full), `performance` (still, puppet, animated) and `lip_sync` (off, cues, baked) are separate choices. A bust presenter can use lip-sync cues; no leaf produces mouth cues on its own, and a talking model is not generated.
- Worlds (`theme`): studio, classroom, workbench, abstract-space. Media (`style`): flat-vector, paper-cut, mixed-media, picture-book, cartoon, chalkboard, blueprint, isometric, one-line. Described values are valid.
- Character art and narration (finished WAV or Mix bundle) come from elsewhere; a missing required asset stays pending.
- Not expressible: UI tours, ads, music videos, generated media, rig creation.

## Where directions go

- Authored video: the producer writes the storyboard. The direction travels in `note` (plus `theme`, `style`, `framing`, `performance`) with named techniques from video-creator's `references/motion-vocabulary.md`: `skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary.md")`; depth work: `references/three-graphics.md` in the same skill.
- Option vocabulary: one file per option under `references/themes/`, `references/styles/`, `references/direction/` of `create-explainer-video`, e.g. `skill_view(name="create-explainer-video", file_path="references/styles/chalkboard.md")`; `references/character.md` and `references/motion-canvas.md` cover presenter and engine.

## Boundaries

- UI task walkthrough: [tour](tour.md). Persuasion toward an action: [ad](ad.md). Characters acting a narrative: [story](story.md). Brand or product presentation: [promotion](promotion.md).
- Character art: [mascot](../image-creator/mascot.md). Narration: [speech](../audio-creator/speech.md).

## Examples

No stored example; propose the leaf's representative sample unit: a short storyboard-approved draft of one topic, with a preview before the full render.
