---
name: creator-logo-icons
description: >-
  Creator's deterministic leaf technic for deriving favicon, Apple, PWA,
  maskable, and app-icon sets from an existing first-party SVG logo. Never
  redraws or image-generates the mark.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, logo, favicon, app-icon, svg]
    category: technic
---

<Goal>

Turn an approved first-party logo master into exact, internally consistent icon
files. This technic is deterministic and consumes zero generation Budget.

</Goal>

<Scope>

Use for favicon, Apple touch icon, PWA, maskable, and platform app-icon sets.
For a third-party mark, use `creator-brand-asset-sourcing`; never derive a new
trademark from an unofficial or generated source.

</Scope>

<Procedure>

1. Load `references/icons.md` and validate the source SVG, destination list,
   background, currentColor handling, and safe-zone requirements.
2. Run `${HERMES_SKILL_DIR}/scripts/logo-to-icons.sh` with explicit color and
   background parameters.
3. Verify every expected file, dimension, alpha/background rule, and 16 px
   legibility. Compare the rendered mark across sizes for identity.
4. Deliver only the requested icon set plus the unmodified SVG anchor.

</Procedure>

<Verification>

- No `image_generate` or invented/redrawn mark was used.
- All requested sizes and formats exist and decode.
- Apple output is flattened; maskable output respects its safe zone.
- The smallest icon remains recognizable and the mark is identical across sizes.

</Verification>
