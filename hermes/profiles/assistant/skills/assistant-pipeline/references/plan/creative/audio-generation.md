# Generated audio — decision surface

AudioCraft instrumental music, ambience, and sound effects. Vocal
songs → `song-generation.md`; speech → `voice.md`; views of existing
audio → `audio-visualization.md`.

Technic `creator-audio-generation` · QA `audio` · metered local
MusicGen/AudioGen compute · resident-only.

## Fix before release

- Mode: `music` (text-conditioned) / `melody` / `style`
  (reference-conditioned) / `sound-effect` (ambience/SFX).
- Duration, structure/sections, mood/genre/instrumentation — and
  prohibited styles or living-artist imitation.
- Conditioning references: their provenance and rights (a supplied
  melody you don't own is a user decision, not a creator judgment).
- Output contract: format, sample rate, channels, loudness/peak,
  looping/fades.
- Runtime grant: local neural compute defaults to ≤15 min/render on
  GPU; a longer estimate needs `Runtime: <=<minutes>/render`, a
  CPU-only path needs `CPU fallback: allowed`, and model-weight
  downloads need explicit authorization — all fixed here, not
  discovered at model load.

## Defaults

- Anchor: for a high-cost or multi-track set, one short sample
  locks prompt/model/seed/sampling before full renders
  (`asset-set.md`).
- Budget shape: 2 renders per asset (failed runs count), 1
  corrective pass.
