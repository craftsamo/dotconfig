---
name: media-craft-visual
description: >-
  Use when creating, revising, or critiquing a visual image asset: a card,
  icon, emoji, mascot, UI kit piece, or a reimagined version of an existing
  image (redesign this mascot, review this icon set, why does this card feel
  busy, restyle this emoji, critique the kit, reimagine this poster). Supplies
  portable composition, typography, surface/light, symbol, and system-asset
  knowledge plus generation-prompt craft, each backed by original worked
  textual worked examples. Owns visual execution of a chosen effect; concept
  selection belongs to direction. Does not cover pure file-format conversion (PNG to SVG,
  resizing, re-export) or edits that carry no visual decision (renaming a
  layer, changing metadata, cropping to a required size with no other change).
license: MIT
---

# Media Craft: Visual

Visual image work is a design decision, not a filter pass. Before changing
pixels, name the one or two problems the request is actually about (weak
hierarchy, muddy edges, an inconsistent pose, a kit that reads as random
components) and revise those, not everything you notice.

There is no single house look. A dense, editorial layout and a calm, spacious
one can both be correct answers to different requests; so can a flat mascot
and a painterly one. Pick the direction the request and the surrounding brand
material call for, and say why you picked it.

## Which reference to read

Read only the reference that matches the actual problem or request; do not
read all six for a small fix.

- Overall layout, hierarchy, grouping, or negative space feels off (a card,
  poster, or slide is busy, flat, or hard to scan): read
  [references/composition.md](references/composition.md).
- Text in the image (labels, wordmarks, captions, a masthead) needs a weight,
  width, leading, or alignment decision, or someone asks for text to be
  "bigger" or "smaller" without a stated reason: read
  [references/typography.md](references/typography.md).
- The surface itself looks flat, plasticky, muddy, or over-textured (adding
  grain or a gradient did not fix the actual problem): read
  [references/surface-light.md](references/surface-light.md).
- The subject is a small silhouette, an icon, an emoji, or a character
  (mascot, avatar) and gesture, expression, pose consistency, or optical
  weight at small size is the issue: read
  [references/symbols-characters.md](references/symbols-characters.md).
- The asset is part of a UI kit, component set, badge system, or 9-slice/atlas
  asset, and consistency, states, or fidelity-vs-geometry tradeoffs are the
  issue: read [references/systems-assets.md](references/systems-assets.md).
- The work happens through a text-to-image or image-editing prompt, or an
  exact piece of copy has to survive into the image: read
  [references/generation.md](references/generation.md).

## Rules that apply everywhere

- A specific leaf brief, an explicit user constraint, or an existing style
  guide always wins over a general craft recommendation here. Offer a
  conflicting recommendation as a proposal, not a silent override.
- Review evidence means looking at the actual pixels at native resolution and
  at the size the asset will actually be used (a 16px icon, a card thumbnail).
  If you can only view it downsized, say so instead of stating a size claim
  you did not check. Never claim an aesthetic result from source code, a
  prompt, or a file hash alone; render or open the actual image first.
- This skill supplies knowledge only. It does not grant permission to render,
  generate, upload, or approve an asset; that authority belongs to the calling
  workflow.
- The worked cases in each reference are illustrative, not a checklist to copy
  verbatim onto an unrelated request; use the diagnosis method, not the exact
  fix, when the situation differs.
