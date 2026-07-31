---
name: creator-text-card
description: >-
  Creator's deterministic leaf technic for OG, social, and title cards whose
  exact text and typography must render correctly over a supplied or separately
  generated background.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, og-image, social-card, typography, composition]
    category: technic
---

<Goal>

Compose exact copy with real fonts and deterministic layout. Generated models
never render the final text.

</Goal>

<Inputs>

The MediaBrief must provide exact copy, target dimensions, safe area, font,
palette, and one of: a supplied background, a solid/gradient direction, or an
explicitly budgeted background from `creator-generated-image`.

</Inputs>

<Procedure>

1. Load `references/text-cards.md`; preserve the user's copy verbatim.
2. If a generated background is required, use `creator-generated-image` as an
   explicitly loaded supporting technic and keep a calm text-safe region.
3. Compose with `${HERMES_SKILL_DIR}/scripts/text-card.sh`.
4. Inspect the native render and a small unfurl preview; read every rendered
   word back against the canonical copy.

</Procedure>

<Verification>

- Dimensions and format match the destination exactly.
- Every character, line break, and brand term matches the supplied copy.
- Text is inside the safe area with no clipping or accidental crop.
- Font, contrast, hierarchy, and thumbnail legibility pass visual inspection.
- Any generated-background spend is accounted for separately in the Budget.

</Verification>
