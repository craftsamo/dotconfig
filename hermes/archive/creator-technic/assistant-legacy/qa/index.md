# Legacy creative - QA routes

Use ONLY for explicitly user-requested inspection of a Creator-confirmed legacy
family. The [requested inspection](../../SKILL.md) scope and
[common QA floor](../../../references/quality-assurance/index.md) apply, without
an automatic revision loop. Normal work uses
[legacy delivery](../../../execute-assistant-creative/references/legacy/index.md),
not these per-unit inspections.

Each contract is read-only inspection against the released unit. For a
composite, inspect only the requested parts or the assembled result using
assembly.md; do not expand the scope or repeat already valid part checks.
Return findings rather than repairing media.

## Legacy families

| Deliverable family | Contract | Covers (canonical) |
| --- | --- | --- |
| Generated raster image or illustration set | `raster-image.md` | `creator-generated-image`, `creator-article-illustration` |
| Infographic | `infographic.md` | `creator-infographic` |
| SVG diagram | `svg-diagram.md` | `creator-svg-diagram` |
| Excalidraw diagram | `excalidraw-diagram.md` | `creator-excalidraw-diagram` |
| Retained text-card identity / meme | `text-visual.md` | `creator-text-card`, `creator-meme` |
| ASCII art | `ascii-art.md` | `creator-ascii-art` |
| Legacy generated video / Manim | `video.md` | `creator-generated-video`, `creator-manim-explainer` |
| Browser-native media | `browser-media.md` | `creator-html-motion`, `creator-p5js-experience` |
| ASCII video | `ascii-video.md` | `creator-ascii-video` |
| Pixel art | `pixel-art.md` | `creator-pixel-art` |
| Pixel animation | `pixel-video.md` | `creator-pixel-video` |
| Comic | `comic.md` | `creator-knowledge-comic` |
| Sourced third-party asset | `sourced-asset.md` | `creator-gif-sourcing`, `creator-brand-asset-sourcing` |
| Assembled composite | `assembly.md` | `creator-media-assembly` |

Route by deliverable and actual method, not file extension. More than one
contract may apply. Styles are job criteria, never separate QA contracts.
An unmapped legacy result requires a decision grounded with Creator; it is
not permission for a generic pass. This mapping says nothing about whether
a normal hands-served deliverable is available or verifiable.

`data-visualization.md` remains generic infrastructure for axes, scales and
source reconciliation; no canonical family currently maps to it. Speech and
instrumental music are hands-served. Vocal-song generation and standalone
audio visualization have no replacement; do not revive them through this file.

## Backend conformance

Compare a named Backend with Creator's capability handshake and report. An
approved core provider chain may fall through its members and still conform
to that core identity. An explicit local ComfyUI workflow must be the one
actually used, not a Partner API node or a silent cloud substitution.

For ComfyUI require the approved loopback host, source workflow SHA-256,
runner result and same-host raw history. Reconcile a separately recorded
effective-graph hash and semantic structure with only the reported parameter
injections. Missing history, unaudited/API/Partner nodes or absent trust/source
review for non-core custom nodes cannot substantiate the approved local
backend. A route mismatch fails even when the visible artifact looks correct.
