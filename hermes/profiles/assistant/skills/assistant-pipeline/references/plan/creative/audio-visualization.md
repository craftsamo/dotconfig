# Audio visualization — decision surface

Deterministic views of **existing** audio: spectrogram, mel, chroma,
hpss, self-similarity, loudness, tempogram, MFCC, flux. Never audio
generation — creating the audio is `audio-generation.md` /
`song-generation.md` / `voice.md`.

Technic `creator-audio-visualization` · QA `data-visualization` ·
deterministic `songsee` render, zero generation spend · card:
`deterministic-render`.

## Fix before release

- The source audio (path) and the time slice — whole file or an
  exact range that exists.
- The visualization list and layout: which views, single or
  multi-panel, and what question the visual should answer (a
  loudness dispute needs different panels than a "what does this
  song look like" post).
- Style, width × height, output format.

## Defaults

- Anchor: none — deterministic and reproducible from the recorded
  command.
- Budget shape: zero generation. If the source needs format
  conversion, that is declared, not improvised.
