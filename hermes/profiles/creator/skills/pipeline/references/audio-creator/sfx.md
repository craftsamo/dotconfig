# audio-creator: sfx

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-sfx` — one short SFX synthesized deterministically from a closed set of eight local waveform kernels; no model, no network.
- `generate-sfx` — one SFX from a prompt, by the local Stable Audio 3 Medium engine (default) or an explicitly chosen fal ElevenLabs SFX v2 engine.
- `edit-sfx` — trims, pitch-shifts, reverses, pads, fades, normalizes or converts one existing SFX into a new master.
- `analyze-sfx` — findings on an existing SFX: native format, loudness, clipping, silence.

## Range

- Kernels (`kind`): click, beep, chime, whoosh, riser, pop, ui-tick, noise-burst; 0.01–22 s, pitch 40–8000 Hz. A real-world sound is never approximated by a kernel.
- Generated: any described sound (a door creak, a crowd cheer, an engine start) in 0.5–21.5 s, given verbatim as the prompt. Local takes a seed and rejects `loop` and `prompt_influence`; the fal engine allows both and takes no seed.
- Edits: pitch in semitones, reverse, padding, fades, peak target, mp3/ogg conversion.
- Not expressible: music, speech, loop-to-length stretching, multi-source concatenation, a proof of a seamless loop.

## Where directions go

- Kernel: `kind`, `seconds`, `pitch`, `seed`; one file per kind under `references/kind/` of `create-sfx`, e.g. `skill_view(name="create-sfx", file_path="references/kind/whoosh.md")`.
- Generated: the `sound` text and `seconds`, `engine`, `loop`, `prompt_influence`; no option vocabulary. `what_for` and `note` carry the rest.

## Boundaries

- Instrumental music: [music](music.md). Spoken words: [speech](speech.md). Several sounds placed in time: [mix](mix.md).
- Sound under picture, such as UI beats: [tour](../video-creator/tour.md), [promotion](../video-creator/promotion.md).

## Examples

No stored example; propose the leaf's representative sample unit: one short SFX (a kernel for a UI tone, or a described sound), a few seconds long.
