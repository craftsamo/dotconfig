---
name: creator-infographic
description: >-
  Creator's leaf technic for information-led infographics using the official
  baoyu-infographic engine, with faithful content and measured image spend.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, infographic, information-design, image-generation]
    category: technic
---

<Goal>

Produce a readable infographic whose layout and style serve the information.
The canonical dispatch identity is `creator-infographic`; the official
`baoyu-infographic` skill is the implementation engine, not a copied playbook.

</Goal>

<Routing>

Use the official engine for information-led image generation with a clear
layout x style grammar. Route dense exact text, precise labels, or number-table
work to `creator-svg-diagram` instead. Never expose secrets in prompts,
structured content, analysis, or generated assets.

</Routing>

<Contract>

`creator-pipeline` owns the MediaBrief, Budget, Review gate, delivery, and one
single batched `Q<n>:` block. Never call the official skill's `clarify`; replace
its material questions with that pipeline block. Load the engine from
`external_dirs` using `skill_view(name="baoyu-infographic")`.

</Contract>

<Procedure>

1. Read the validated brief and preflight the engine, source data, destination,
   ratio options, and image render/vision path. Block before production or
   acceptance if a dependency or render path is unavailable.
2. Lock the layout x style grammar and preserve information fidelity. Save the
   prompt, analysis, and structured-content artifacts before calling
   `image_generate`; reconcile every call with the granted Budget.
3. For a custom ratio, choose the closest supported enum, generate, then
   normalize to the requested output without changing data or content.
4. Inspect the actual image with vision and read every rendered word, number,
   label, and legend back against the source. Save the final image and evidence.
5. Attach final artifacts and hand V1-V6 evidence to the pipeline for Review and
   delivery; do not treat an unverified image as complete.

</Procedure>

<Verification>

- Layout, style grammar, information order, data values, hierarchy, contrast,
  crop, dimensions, and format match the brief.
- Every generated character is readable and faithful; unreadable or altered
  data routes to SVG or blocks rather than being silently accepted.
- Record generation spend and failed attempts for V5, then provide V1
  acceptance, V2 mechanical, V3 visual, V4 consistency, and V6 attachment
  evidence to `creator-pipeline`.

</Verification>
