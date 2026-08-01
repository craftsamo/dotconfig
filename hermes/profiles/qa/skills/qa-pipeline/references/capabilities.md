# QA capability routing

This is the authoritative mapping from a completed producer capability to one
or more independently pinnable QA technics. The QA pipeline owns target
resolution, common acceptance checks, Researcher evidence reconciliation, and
verdict roll-up. Each leaf owns one distinct inspection contract.

## Canonical routes

| Producer capability / deliverable | Canonical QA technic | Composition notes |
| --- | --- | --- |
| `creator-generated-image` | `qa-raster-image` | Actual raster, native size, destination crop and thumbnail |
| `creator-article-illustration` | `qa-raster-image` | Also apply the illustration-set mode for placement and cross-image consistency |
| `creator-infographic` | `qa-infographic` | Information hierarchy, label/data fidelity, legibility |
| `creator-svg-diagram` | `qa-svg-diagram` | Source structure plus rendered preview |
| `creator-excalidraw-diagram` | `qa-excalidraw-diagram` | JSON/editability plus rendered preview |
| `creator-logo-icons` | `qa-icon-set` | Source fidelity, complete size/maskable set |
| `creator-text-card` | `qa-text-visual` | Exact copy readback, typography and safe areas |
| `creator-meme` | `qa-text-visual` | Add `qa-sourced-asset` when a sourced template is used |
| `creator-meme` | `qa-sourced-asset` | Conditional: sourced template provenance package |
| `creator-ascii-art` | `qa-ascii-art` | UTF-8 text master and terminal geometry |
| `creator-audio-visualization` | `qa-data-visualization` | Source-to-render correspondence and measured labels |
| `creator-audio-generation` | `qa-audio` | Instrumental, ambience, and SFX integrity |
| `creator-song-generation` | `qa-song` | Lyrics, vocal structure, and audio integrity |
| `creator-gif-sourcing` | `qa-sourced-asset` | Source identity, provenance, and delivery rights caveat |
| `creator-gif-sourcing` | `qa-video` | Animated content, dimensions, timing, and loop behavior |
| `creator-generated-video` | `qa-video` | Sampled temporal inspection plus mechanical probe |
| `creator-html-motion` | `qa-browser-media` | Runnable source, states, viewport, console and deterministic timeline |
| `creator-html-motion` | `qa-video` | Conditional: required for an exported MP4/WebM/GIF deliverable |
| `creator-p5js-experience` | `qa-browser-media` | Interaction, resize, deterministic seed and representative states |
| `creator-p5js-experience` | `qa-video` | Conditional: required for an exported time-based deliverable |
| `creator-ascii-video` | `qa-ascii-video` | Temporal text geometry, glyph stability, audio sync when present |
| `creator-manim-explainer` | `qa-video` | Use explainer mode; factual/math claims require a Researcher parent |
| `creator-pixel-art` | `qa-pixel-art` | Native grid, fixed palette, anti-alias and integer preview checks |
| `creator-pixel-video` | `qa-pixel-video` | Pixel-grid checks over time plus loop/temporal integrity |
| `creator-knowledge-comic` | `qa-comic` | Panel sequence, lettering, continuity, source-backed claims |
| `creator-brand-asset-sourcing` | `qa-sourced-asset` | First-party identity, provenance package and unchanged asset |
| `core:tts` | `qa-voice` | Verbatim back-transcription plus audio delivery checks |
| `writer:marketing-copy` | `qa-prose` | Marketing-copy type contract |
| `writer:technical-prose` | `qa-prose` | Article/tutorial argumentation and reader-flow contract |
| `writer:documentation` | `qa-prose` | Scannable documentation type contract |
| `writer:script` | `qa-script` | Unit integrity, production constraints and verbatim boundaries |

## Selection rules

1. Route from the producer's canonical capability and actual final deliverable,
   not the extension alone.
2. Pin every unconditional route and every conditional route triggered by the
   requested output. A card may pin multiple QA technics.
3. Styles and presets are criteria, not technics. NES, Game Boy, PICO-8,
   palette names, aspect ratios, platforms, and house style stay in the brief.
4. A reference is an internal mode only when target access, tools, evidence,
   and verdict rules remain the same. A different inspection contract becomes
   another flat `qa-*` technic.
5. External facts, current platform rules, citations, provenance truth, and
   mathematical/factual claims require a predeclared Researcher parent. QA
   still checks that the final artifact represents that evidence accurately.
6. An unknown producer capability or missing required pin is `can't_verify`.
   Never route it to `qa-raster-image` or another generic leaf by resemblance.
