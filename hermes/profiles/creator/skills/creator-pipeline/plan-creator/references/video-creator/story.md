# Plan — video-creator: story

Read [common plan](../../SKILL.md) first.

`create-story` is the served route for a short character story (10..120 s):
recurring characters from their approved art act out a narrative across
scenes, with dialogue from an approved script and a finished soundtrack,
staged by VideoCreator as 2.5D HTML animation. It is not a learning
explanation with a character ([explainer-video](explainer-video.md)), a
piece that presents a product or place ([promotion](promotion.md)), a
model-generated MV ([music-video](music-video.md)) or a generated shot
([clip](clip.md)). Characters are never generated per scene: generated
video drifts from the approved art.

Settle with the client: premise (setup, turn, ending), purpose and viewer,
aspect and length, the cast, the world and its look. The cast means
approved art that already exists — a mascot anchor and its pose pack, or
supplied character images. An unspecified cast is not "no cast": clarify
existing characters vs. new ones. New characters and missing poses are
image-creator mascot units (a new design, or a round-B `pack: custom` of
the missing poses on the approved anchor) before or alongside the
storyboard. Tell the client up
front there is no lip sync: speaking is staged with poses, expressions and
timing.

Plan the dependency order as separate units: script through Writer's
write-script (every spoken and on-screen line), cast art through
image-creator, then the storyboard approval, then voices through
audio-creator's generate-speech per line and create-mix for lines, music
and SFX on the storyboard's timeline (captions come with the Mix when the
speech has word timing). A pending storyboard is a useful preliminary plan;
dependencies can be released once it names what they need.
