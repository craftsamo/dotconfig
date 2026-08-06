# QA contracts — index and common floor

Load from <ModeQA> when verifying a specialist deliverable. Pick the
contract file(s) by the deliverable family below; every contract is a
read-only inspection you (the assistant) run yourself — with
`delegate_task` fanning out per-artifact checks when the set is large.

## Common floor (every verification)

- **Inspect the actual artifact**, never the producer's description of it:
  open the file at its durable path, hash-check nothing is stale, and
  measure what the brief specifies (dimensions, duration, format, count).
- **Judge against the brief**: the settled done criteria, style anchors,
  and platform constraints — not your own taste. Taste calls belong to the
  user; contract violations belong to feedback.
- **Findings are itemized evidence**: per artifact — what was checked, the
  measured/observed value, and the defect (with timecode/coordinates/
  quote) or the pass. An unnamed check didn't happen.
- **External facts need evidence**: claims, citations, provenance, math —
  require the research evidence supplied in the flow; QA checks the
  artifact represents that evidence accurately, it does not re-research.
- **Never repair**: no editing, re-encoding, cropping, rewriting, or
  regeneration during verification. Defects go back to the producing
  session as itemized feedback.
- **Cannot verify ≠ pass**: an unreadable file, missing evidence, or an
  unknown deliverable family means NOT verified — obtain what is missing
  (or say plainly it cannot be checked); never deliver on resemblance.

## Routes

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
| Prose (copy, article, documentation) | `prose.md` | type contract per writer type |
| Script / storyboard / screenplay | `script.md` | unit integrity, production constraints, verbatim boundaries |

Selection rules:

1. Route from the actual final deliverable, not the file extension alone;
   one deliverable may need several contracts (e.g. p5.js + exported MP4).
2. Styles and presets (NES, PICO-8, palette names, aspect ratios, house
   style) are criteria inside the brief, not separate contracts.
3. Engineering deliverables have no file here — their gate is the
   engineer's own verification engine plus your outcome-level check
   (`references/engineering.md`).
