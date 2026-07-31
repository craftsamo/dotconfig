---
name: creator-pixel-art
description: >-
  Creator's deterministic leaf technic for pixel-art stills: source reduction
  or native-grid drawing, fixed palettes, no anti-aliasing, batch palette locks,
  and native plus nearest-neighbor preview delivery. External pixel-art skills
  are optional implementation backends, never dispatch identities.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, pixel-art, sprite, limited-palette, deterministic]
    category: technic
---

<Goal>

Deliver intentional pixel art whose grid, palette, edges, and source fidelity
survive measurement. The native-resolution PNG is the master; a
nearest-neighbor upscale is the human review copy.

</Goal>

<Scope>

Use when the final deliverable is a still pixel asset: sprite, avatar, icon,
logo reduction, scene, or limited-palette illustration. Animation belongs to
`creator-pixel-video`.

</Scope>

<Inputs>

Before work, the pipeline MediaBrief must pin:

- source asset or permission/Budget to create a base with
  `creator-generated-image`,
- native grid `W x H` and destination upscale,
- named/fixed palette or a palette color cap,
- source-fidelity vs deliberate-redraw intent,
- transparency, tile/sprite-sheet, and batch consistency requirements.

A thin logo, glyph, diagonal, or circular mark needs a grid-size fork before
production. Do not discover at review that the requested grid cannot carry it.

<Backend>

The canonical skill is this file. A compatible `pixel_art.py` may be used as an
implementation backend when found under `~/.agents/skills/pixel-art` or the
Hermes optional-skill checkout. Never `skill_view` or pin the ambiguous bare
name `pixel-art`. Record the exact backend path in the first `STATE:` comment.

`scripts/render-pixel-art.sh` performs that preflight, uses the shared opted-in
backend before the official checkout fallback, verifies its required CLI, and
produces a native master plus review upscale. It exposes cover/contain, gravity,
background, and preserve/flatten/reject alpha policy; never accept its defaults
when the Brief pins a different crop or transparency contract. Hand-authored
geometry may instead be drawn directly on the native grid with Pillow under the
same verification floor.

</Backend>

<Procedure>

1. Inspect the source and choose reduction vs native-grid redraw.
2. Lock grid, palette, crop, transparency, and protected source features.
3. Produce the native PNG. Never rotate or resample a finished pixel bitmap.
4. Produce the review copy by integer nearest-neighbor scaling only.
5. For a batch, reuse one named palette or apply one approved sample with
   `uv run --no-project --with Pillow python
   ${HERMES_SKILL_DIR}/scripts/palette-extract.py apply ... --grid WxH`;
   never adaptively quantize each item independently.
6. Inspect both files and report the weakest legibility point honestly.

</Procedure>

<Verification>

- Native dimensions equal the brief's grid exactly.
- Color count is within the locked palette and no intermediate anti-aliased
  colors appear.
- Preview dimensions are an integer multiple of the native grid and every
  source pixel becomes one uniform block.
- Protected silhouettes, glyphs, transparency, and proportions remain correct.
- Batch items use the identical palette anchor.
- Native master, preview, palette/seed, and any reusable source are attached.

</Verification>
