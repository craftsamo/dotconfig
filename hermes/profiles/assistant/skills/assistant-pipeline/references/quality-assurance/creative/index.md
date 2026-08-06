# Creative QA contracts — routes

Pick the contract file(s) by the deliverable family; every contract is a
read-only inspection you run yourself — with `delegate_task` fanning out
per-artifact checks when the set is large. The common floor in
`../index.md` always applies.

| Deliverable family | Contract | Notes |
| --- | --- | --- |
| Generated raster image (cover, hero, illustration, thumbnail) | `raster-image.md` | native size, destination crop, set consistency |
| Infographic | `infographic.md` | information hierarchy, label/data fidelity, legibility |
| SVG diagram | `svg-diagram.md` | source structure plus rendered preview |
| Excalidraw diagram | `excalidraw-diagram.md` | JSON/editability plus rendered preview |
| Icon / logo set | `icon-set.md` | source fidelity, complete size/maskable set |
| Text card / meme (exact copy on image) | `text-visual.md` | exact copy readback, typography, safe areas; sourced template → also `sourced-asset.md` |
| ASCII art | `ascii-art.md` | UTF-8 text master and terminal geometry |
| Data visualization | `data-visualization.md` | source-to-render correspondence, measured labels |
| Generated audio / ambience / SFX | `audio.md` | integrity, duration, levels |
| Song (music + vocals) | `song.md` | lyrics, vocal structure, audio integrity |
| Voice line (TTS) | `voice.md` | verbatim back-transcription plus delivery checks |
| Video (generated, sourced GIF, Manim explainer) | `video.md` | sampled temporal inspection plus mechanical probe; explainer claims need evidence |
| Browser-native media (HTML motion, p5.js) | `browser-media.md` | runnable source, states, deterministic timeline; exported av → also `video.md` |
| ASCII video | `ascii-video.md` | temporal text geometry, glyph stability |
| Pixel art still | `pixel-art.md` | native grid, fixed palette, integer preview |
| Pixel animation | `pixel-video.md` | pixel-grid checks over time, loop integrity |
| Comic | `comic.md` | panel sequence, lettering, continuity, source-backed claims |
| Sourced third-party asset (GIF, brand mark) | `sourced-asset.md` | identity, provenance, rights caveat, unchanged asset |
