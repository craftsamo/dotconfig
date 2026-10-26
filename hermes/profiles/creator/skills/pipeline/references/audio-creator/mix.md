# audio-creator: mix

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-mix` — already-finished speech, sfx and music sources combined into one placed, gain-automated master on a shared timeline; a proposal comes first.
- `edit-mix` — revises one existing mix bundle (placement, gain, fades, added or removed cues, duration or loudness target) from a plain-language change request.
- `analyze-mix` — format, loudness, clipping and true-peak findings on any finished mix, plus the recorded cue placement when its own bundle is supplied.

## Range

- 1–16 finished sources, up to 32 cues, up to 600 s; one 48 kHz master, with optional word timing, captions and SRT.
- Placement, gain, fades and envelope automation are authored from stated intent (what leads, what layers underneath, ducking and pacing), or supplied exactly and kept verbatim.
- Loudness target is an explicit authored choice.
- Not expressible: new sound synthesis, looping a source to length, EQ, reverb, stem separation from a master, video assembly.
- Needs the component sounds to exist first: [speech](speech.md), [sfx](sfx.md), [music](music.md).

## Where directions go

- `what_for`, `direction` (how cues relate), `duration`, `must_keep`, `timing`, `arrangement`, `note`; for a revision, `changes`.
- Vocabulary for exact arrangements: `skill_view(name="create-mix", file_path="references/arrangement.md")`; there are no option files.

## Boundaries

- Sounds not yet made go to their own leaves first. A defect inside one source is fixed by editing that source, not here.
- Joining picture and soundtrack: [master](../video-creator/master.md). Soundtracks for authored video: [ad](../video-creator/ad.md), [tour](../video-creator/tour.md), [story](../video-creator/story.md).

## Examples

No stored example; propose the leaf's representative sample unit: the numbered proposal and a short mix of two or three finished sources with one cue layering.
