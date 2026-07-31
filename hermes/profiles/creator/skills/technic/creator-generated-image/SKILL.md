---
name: creator-generated-image
description: >-
  Creator's leaf technic for metered, text-free image generation: covers,
  heroes, illustrations, thumbnails, social backgrounds, and document art.
  The creator-pipeline owns intake, Budget, review, and delivery; this skill
  owns prompt construction, image_generate, exact export, and image-specific QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, image-generation, illustration, branding]
    category: technic
---

<Goal>

Produce a text-free generated image that fits its destination and visual
system. This is a leaf technic, not an asset router: `creator-pipeline` selects
it only when generative imagery is the primary production method.

</Goal>

<Scope>

Use for generated covers, hero art, illustrations, thumbnails, social
backgrounds, and slide/document art. Do not use for:

- favicon/app-icon sets derived from an existing logo (`creator-logo-icons`),
- exact text cards (`creator-text-card`),
- pixel-art output (`creator-pixel-art`), or
- deterministic HTML/CSS motion (`hyperframes`).

</Scope>

<Inputs>

The card's MediaBrief, validated by `creator-pipeline`, must pin purpose,
audience, destination, dimensions/aspect/crop behavior, format/size cap,
style or brand inputs, count, and Budget. Missing material direction follows
the pipeline's single batched `Q<n>:` block protocol; never call `clarify`.

</Inputs>

<Procedure>

1. Load `references/ai-imagery.md`; also load `references/social-specs.md` or
   `references/docs.md` when the destination needs it.
2. Build one reusable style block from the brief. Keep exact text, letters,
   numbers, and logos out of the generated pixels.
3. Save every final prompt to `prompts/NN-<slug>.md` before spending.
4. Call `image_generate` within the effective Budget. The configured provider
   chain owns backend choice; never hardcode a model into the prompt.
5. Normalize each selected result with
   `${HERMES_SKILL_DIR}/scripts/img-postprocess.sh` to exact dimensions,
   format, crop, and size cap.
6. Inspect the actual file at native size, destination crop, and thumbnail
   size. Use the pipeline's corrective allowance only for a brief miss.

</Procedure>

<Verification>

- Prompt and generation count reconcile with the pipeline spend tally.
- Dimensions, format, crop behavior, and file-size cap are measured.
- Every output is visually inspected for artifacts, anatomy/geometry errors,
  accidental text/logos, composition, contrast, and brief adherence.
- A batch reuses the locked style block verbatim; only its subject changes.
- Final files and reusable prompt/style anchors flow through the pipeline's
  attachment and delivery contract.

</Verification>

<Files>

- `references/ai-imagery.md` - prompt structure and tuning.
- `references/social-specs.md` - social-image target specs.
- `references/docs.md` - slide/document/print considerations.
- `scripts/img-postprocess.sh` - normalize, resize/crop, encode, and size-cap.

</Files>
