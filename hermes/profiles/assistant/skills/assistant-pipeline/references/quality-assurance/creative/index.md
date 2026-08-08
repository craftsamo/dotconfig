# Creative QA contracts — routes

Pick the contract file(s) by the deliverable family; every contract
is a read-only inspection you run yourself — with `delegate_task`
fanning out per-artifact checks when the set is large. The common
floor in `../index.md` always applies.

Contracts are keyed by **inspection method**, so several canonical
families may share one contract; the Covers column is the total
mapping (validator-checked — every canonical technic appears exactly
once). In a composite, **every part gates on its own contract when
its unit completes**; the assembled final gates on `assembly.md` —
part checks are not repeated there.

| Deliverable family | Contract | Covers (canonical) |
| --- | --- | --- |
| Generated raster image (cover, hero, illustration, set) | `raster-image.md` | `creator-generated-image`, `creator-article-illustration` |
| Infographic | `infographic.md` | `creator-infographic` |
| SVG diagram | `svg-diagram.md` | `creator-svg-diagram` |
| Excalidraw diagram | `excalidraw-diagram.md` | `creator-excalidraw-diagram` |
| Icon / logo set | `icon-set.md` | `creator-logo-icons` |
| Text card / meme (exact copy on image) | `text-visual.md` | `creator-text-card`, `creator-meme` |
| ASCII art | `ascii-art.md` | `creator-ascii-art` |
| Data visualization | `data-visualization.md` | `creator-audio-visualization` |
| Generated audio / ambience / SFX | `audio.md` | `creator-audio-generation` |
| Song (music + vocals) | `song.md` | `creator-song-generation` |
| Voice line (TTS) | `voice.md` | `core:tts` |
| Video (generated, Manim explainer, GIF export) | `video.md` | `creator-generated-video`, `creator-manim-explainer` |
| Browser-native media (HTML motion, p5.js) | `browser-media.md` | `creator-html-motion`, `creator-p5js-experience` |
| ASCII video | `ascii-video.md` | `creator-ascii-video` |
| Pixel art still | `pixel-art.md` | `creator-pixel-art` |
| Pixel animation | `pixel-video.md` | `creator-pixel-video` |
| Comic | `comic.md` | `creator-knowledge-comic` |
| Sourced third-party asset (GIF, brand mark) | `sourced-asset.md` | `creator-gif-sourcing`, `creator-brand-asset-sourcing` |
| Assembled composite (mux/concat/mix/overlay) | `assembly.md` | `creator-media-assembly` |

Selection rules:

1. Route from the actual final deliverable, not the file extension
   alone; one deliverable may need several contracts (e.g. p5.js +
   exported MP4).
2. Styles and presets (NES, PICO-8, palette names, aspect ratios,
   house style) are criteria inside the brief, not separate
   contracts.
3. An unmapped deliverable family is NOT verifiable — say so and
   decide with the user; never fall back to a generic look-over for
   a publishing deliverable.
