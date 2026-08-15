---
name: creator-generated-image
description: >-
  Creator's leaf technic for metered, text-free image generation: covers,
  heroes, illustrations, thumbnails, social backgrounds, and document art.
  The creator-pipeline owns intake, Budget, review, and delivery; this skill
  owns prompt construction, selected-backend execution, exact export, and
  image-specific QA.
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
- deterministic HTML/CSS motion (`creator-html-motion`).

</Scope>

<Inputs>

The card's MediaBrief, validated by `creator-pipeline`, must pin purpose,
audience, destination, dimensions/aspect/crop behavior, format/size cap,
style or brand inputs, count, Backend, and Budget. Allowed backends are
`core:image_generate` and `external:comfyui`. Missing material direction or an
open backend follows the pipeline's single batched `Q<n>:` block protocol;
never call `clarify`.

</Inputs>

<Procedure>

1. Load `references/ai-imagery.md`; also load `references/social-specs.md` or
   `references/docs.md` when the destination needs it.
2. Preflight the approved Backend before prompt work:
   - `core:image_generate`: confirm the core tool resolves to the Creator
     profile's configured provider chain. That chain owns its existing internal
     fallback.
   - `external:comfyui`: load `skill_view(name="comfyui")`, resolve its concrete
     scripts, and run its local hardware/server/workflow dependency checks. The
     selected API-format workflow must use local models/nodes only and fit the
     granted runtime. Pin its loopback host and workflow SHA-256, audit every
     `class_type` against that host's `/object_info`, run `extract_schema.py` to
     inspect model/output nodes, and reject API/Partner nodes. Review every
     non-core custom-node source for hidden network/cloud execution unless its
     package is explicitly trusted. A missing server, non-accelerated device,
     model, audited local node package, output node, or executable workflow
     blocks; never substitute core generation or a ComfyUI Partner API node.
3. Build one reusable style block from the brief. Keep exact text, letters,
   numbers, and logos out of the generated pixels.
4. Save every final prompt to `prompts/NN-<slug>.md` before spending. Record the
   approved Backend; for ComfyUI also record the workflow, checkpoint/model,
   seed, sampler, steps, and runtime ceiling required to reproduce the call.
5. Generate within the effective Budget using only the approved Backend:
   - core: call `image_generate`; never hardcode a model into the prompt.
   - ComfyUI: run the preflighted workflow through the external skill's
     `run_workflow.py` path and local host. Each submitted workflow counts as an
     image-generation attempt even though it has zero marginal API cost.
     Preserve the runner JSON and fetch the same-host raw history by `prompt_id`
     so the effective submitted graph and timing remain auditable. Hash that
     graph separately and compare its node IDs/classes/wiring with the source;
     only recorded parameter injections may differ.
6. Normalize each selected result with
   `${HERMES_SKILL_DIR}/scripts/img-postprocess.sh` to exact dimensions,
   format, crop, and size cap.
7. Inspect the actual file at native size, destination crop, and thumbnail
   size. Use the pipeline's corrective allowance only for a brief miss.

</Procedure>

<Verification>

- Prompt and generation count reconcile with the pipeline spend tally.
- The executed Backend matches the MediaBrief and the capability handshake;
  ComfyUI runs name the loopback host, source-workflow hash, effective-graph
  hash, and allowed injection diff. Their raw history proves the submitted
  graph/model/seed without hosted Partner/custom nodes or a cross to core
  generation. Missing history leaves the backend claim unverified.
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
