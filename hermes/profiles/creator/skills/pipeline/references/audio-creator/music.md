# audio-creator: music

Read the [kernel](../../SKILL.md) first. The leaf's form is authoritative; this says what it can express.

## Leaves

- `create-music` — instrumental BGM or a short melodic cue composed as a deterministic electronic score; no model or network; a proposal comes first.
- `generate-music` — the same kind of piece from a described sound, by local Stable Audio 3 Medium (default) or an explicitly chosen paid fal engine; a proposal comes first.
- `edit-music` — trims, repeats to length with a crossfaded loop seam, fades, gain or loudness normalization of one existing file into a new master.
- `analyze-music` — tempo, beat, key, chord and structural-boundary estimates, plus format and loudness, on any existing music file.

## Range

- Created or generated: 1–60 s, instrumental only. `create-music` uses five waveforms (sine, triangle, pulse, fm-bell, noise); `generate-music` reaches real-world and sampled instruments, approximately.
- Mood (`theme`): warm, playful, dreamy, tense, uplifting. Development (`direction`): steady, gradual-build, contrast, motif-return. Closing (`ending`): resolve, fade, loop. Tempo, key, meter, melody and harmony can be named in words.
- `create-music` styles: minimal-electronic, chiptune, ambient-synth. `generate-music` styles: ambient, electronic, lofi, acoustic, jazz, orchestral.
- `reference_audio` is a local reference only, with `reference_focus` saying what to borrow.
- Edits and analysis accept up to 600 s; edits never resynthesize; analysis gives no genre, mood or instrument verdict.
- Not expressible: songs with lyrics or singing, sound effects, mixing.

## Where directions go

- `theme`, `theme_detail`, `style`, `instrumentation`, `direction`, `tempo`, `ending`, `must_keep`, `note`.
- One file per option under `references/themes/`, `references/styles/`, `references/direction/`, `references/ending/` of `create-music` (and `generate-music`), e.g. `skill_view(name="create-music", file_path="references/direction/gradual-build.md")`.

## Boundaries

- Whole songs with lyrics: not served. Short sounds: [sfx](sfx.md). Spoken words: [speech](speech.md). Placing music with speech and effects: [mix](mix.md).
- Music for a generated piece: [music-video](../video-creator/music-video.md); under joined picture: [master](../video-creator/master.md).

## Examples

No stored example; propose the leaf's representative sample unit: the numbered proposal and one short cue (10–20 s) in one mood and style.
