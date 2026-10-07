---
name: creator-article-illustration
description: >-
  Creator's thin adaptation layer for article illustration: analyze an article,
  plan visual placements, generate text-free images, and return safe relative
  links without taking ownership of the article or production pipeline.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, article, illustration, editorial]
    category: technic
---

<Goal>
Use this leaf when an article needs several concept-led illustrations. Keep the
article's meaning and facts intact while making images that support, rather
than literally depict, the argument.
</Goal>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Review, delivery, and questions.
- Never call an official skill's `clarify`; convert missing inputs into one
  batched `Q<n>:` block owned by the pipeline.
- Load optional `baoyu-article-illustrator` only through `external_dirs` with
  `skill_view(name="baoyu-article-illustrator")`; the canonical identity
  remains `creator-article-illustration`.
- Do not carry secrets from source material into prompts, images, or outputs.
- Preserve facts, numbers, labels, and quotations; do not silently rewrite them.
- Save every prompt before generation. Count every `image_generate` attempt,
  including failures, against Budget.
- Download every URL to an absolute path and verify that the resulting file is
  real before review or delivery.
- Exact text belongs in a deterministic composition or a canonical supporting
  technic, never in the image model; record that work and spend separately.
- Honor the pipeline's V1-V6 gates, including per-image vision and batch
  consistency; do not bypass its review or delivery contract.
</Contract>

<Procedure>
1. Read the approved MediaBrief and article without exposing source secrets.
2. Analyze thesis, audience, sections, factual anchors, tone, and candidate
   placements. Produce a placement outline and present it in your reply for
   approval (the anchor stage) — never proceed to generation on your own
   approval.
3. For each placement, lock `Type x Style x Palette`, density, aspect, crop,
   and a concept that is metaphorical or structural rather than literal.
4. Inspect supplied reference images with vision and record reusable traits
   (composition, palette, texture, lighting, and shape language), not hidden
   source content or an unapproved imitation.
5. Write prompt files before any call, then run `image_generate` within Budget.
6. Localize URL results to absolute paths, verify real files, and inspect each
   image with vision at native, destination, and thumbnail sizes.
7. Compare the batch against its locked style block and correct only within the
   pipeline's allowance. Reconcile prompts, attempts, outputs, and spend.
8. Return the reviewed assets and a placement map. Insert relative links into
   the article only when the user explicitly requests source-file modification;
   otherwise provide link instructions or a patch without changing the article.
</Procedure>

<Routing>
- Route exact labels, diagrams, or data-led explanatory visuals to
  `creator-svg-diagram`.
- Route a single visual summary of the whole article to `creator-infographic`.
- Use a canonical supporting technic for deterministic text or composition and
  record it as a separate stage and expense.
</Routing>

<Verification>
- Placement coverage, factual fidelity, density, crop, and destination fit pass.
- No generated image contains required exact text, accidental labels, or secrets.
- Every prompt, failed and successful attempt, absolute download, vision check,
  and relative-link decision is auditable through pipeline V1-V6.
</Verification>
