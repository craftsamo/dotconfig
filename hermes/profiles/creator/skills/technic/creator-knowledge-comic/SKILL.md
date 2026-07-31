---
name: creator-knowledge-comic
description: >-
  Creator's thin adaptation layer for knowledge comics: turn approved source
  material into a reviewed storyboard, consistent character prompts, and
  deterministic, text-accurate comic pages without owning pipeline delivery.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, knowledge-comic, storyboard, sequential-art]
    category: technic
---

<Goal>
Create an educational multi-panel comic whose claims remain faithful to the
source and whose characters, page order, and readable copy survive production.
This is a leaf technic, not a replacement for `creator-pipeline`.
</Goal>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Review, delivery, and questions.
- Never call an official skill's `clarify`; put missing decisions in one batched
  `Q<n>:` block for the pipeline.
- Load optional `baoyu-comic` from `external_dirs` through
  `skill_view(name="baoyu-comic")`; the canonical identity remains
  `creator-knowledge-comic`.
- Keep source secrets out of prompts and deliverables, and preserve facts,
  numbers, labels, and quotations without alteration.
- Save every prompt before generation. Count every `image_generate` attempt,
  including failures, against Budget.
- Download each URL to an absolute path and verify a real file before review.
- Exact dialogue and captions are deterministic post-composition by default;
  ask the image model for art and blank balloons, never final lettering.
- Honor pipeline V1-V6, per-image vision, batch consistency, and its review and
  delivery contract rather than inventing a parallel approval flow.
</Contract>

<Modes>
Support full production, `storyboard-only`, `prompts-only`, `images-only`, and
`regenerate`.
For `images-only`, require an approved storyboard and character definitions;
for `regenerate`, preserve approved copy, panel order, anchors, and constraints.
</Modes>

<Procedure>
1. Analyze source claims, audience, learning sequence, tone, cast, and page
   constraints. Keep an explicit fact/quote ledger for later readback.
2. Build analysis, storyboard, character definitions, page prompts, and page
   deliverables as distinct artifacts. Embed the full character consistency
   definition in every relevant prompt; a character sheet is for human review,
   not an image input.
3. For multi-page work, stop at the plan/anchor gate until the pipeline approves
   page count, reading order, recurring anchors, safe areas, and continuity.
4. Save all page prompts before spending. Generate only within Budget, counting
   failed attempts, then download every page URL to its own absolute path.
5. Inspect each page with vision for panel order, safe area, anatomy, props,
   character consistency, art continuity, and accidental text. Review the batch
   for cross-page consistency and reconcile V1-V6 records.
6. Compose dialogue and captions deterministically with real fonts and exact
   copy, or invoke an appropriate canonical supporting technic as a separately
   recorded stage and expense. Read back every rendered line.
7. Inventory the destination before writing. Never overwrite an existing
   directory: preserve it through the pipeline's backup/inventory procedure.
8. Return reviewed pages, prompts, storyboard, readback, and placement/order
   metadata to the pipeline for delivery; do not publish or alter source files.
</Procedure>

<Verification>
- All claims and quotations match the fact/quote ledger; every dialogue and
  caption line is read back, readable, and exact, with no model-generated
  lettering accepted as final.
- Every page has an absolute verified file, correct panel order, safe area, and
  character continuity, with failed attempts and spend reconciled.
- Regeneration changes only the approved target; existing assets remain backed
  up or inventoried, never silently replaced.
</Verification>
