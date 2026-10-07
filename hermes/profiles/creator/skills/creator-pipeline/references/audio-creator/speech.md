# audio-creator: speech

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `generate-speech` — one approved script (up to 600 characters) spoken as narration or a registered character line; 48 kHz mono WAV, word times, estimated SRT, optional Opus voice message.
- `edit-speech` — concatenates ordered speech tracks, trims boundary silence, adjusts speed, normalizes loudness or converts format; new WAV with updated timing.
- `analyze-speech` — findings on an existing spoken file: format, loudness, clipping, silence, optional script readback; no new asset.

## Range

- Voices: `house` (default) or a registered `<engine>:<id>`; a named voice may take a delivery direction (`style`) or `seed` only when its engine advertises it. Languages: ja, en.
- Output is a spoken take of the exact words; one section per take, longer scripts are split.
- Edits change timing, order, speed and loudness; they do not rewrite words, convert voices or denoise.
- Not expressible: script writing, voice cloning or registration, music, singing, sound effects.

## Where directions go

- `voice` and `language` carry the casting; `style` carries delivery for a qualified voice that advertises it; `note` carries the rest.
- There is no option vocabulary under the leaf; a voice is named by the client or taken from a character's registered voices.

## Boundaries

- Words to be written or rewritten: Writer, not this leaf. Lines placed with music or sound effects on one timeline: [mix](mix.md).
- A sound that is not speech: [sfx](sfx.md). Instrumental music: [music](music.md).
- Speech under picture: [explainer-video](../video-creator/explainer-video.md), [story](../video-creator/story.md), [master](../video-creator/master.md).

## Examples

No stored example; propose the leaf's representative sample unit: a single spoken take of one short approved section in one voice.
