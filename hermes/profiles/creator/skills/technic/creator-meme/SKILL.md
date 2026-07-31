---
name: creator-meme
description: >-
  Creator's deterministic leaf technic for classic-template and custom-scene
  memes with exact caption content, provenance, and visual QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, meme, typography, pillow, provenance]
    category: technic
---

<Goal>
Produce a meme whose joke structure, source image, and caption content survive
deterministic composition. The canonical dispatch identity is `creator-meme`;
the official `meme-generation` skill is its implementation engine.
</Goal>

<Modes>
- `classic-template` - an Imgflip/curated template with known caption fields.
- `custom-scene` - a supplied or separately generated text-free background.
</Modes>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
- Load `skill_view(name="meme-generation")`; never expose that engine as the
  stable dispatch identity or copy its playbook into this leaf.
- Template composition has zero generation spend. A custom generated scene
  loads `creator-generated-image` explicitly and uses a separate Budget line.
- Save final caption strings before rendering. Preserve every character; line
  wrapping is renderer-owned unless the brief marks exact breaks as invariant.
- Never install dependencies. Missing Python, Pillow, mode-required template or
  network access, font coverage, or output permissions blocks production.
</Contract>

<Procedure>
1. Lock premise, audience, tone, destination, mode, and captions. For each
   supplied caption, compare it with `" ".join(caption.split())`; any mismatch
   is an exact whitespace invariant, including leading/trailing, repeated,
   non-breaking, full-width, tab, or newline whitespace.
2. Resolve the official `generate_meme.py` script. For a classic template,
   select by joke structure (dilemma, preference, escalation, denial), not topic
   alone; record name/ID, field count/order, source URL, and rationale.
3. For a custom scene, use a supplied image or load `creator-generated-image`.
   Generate no text and reserve clear caption zones; record generation spend.
4. Keep fields short (normally 8-12 words) and match their order to the
   template. For ordinary single-space captions, render through `python3` plus
   the official script; use bars when an overlay would be unreliable.
5. The official wrapper normalizes whitespace. For any whitespace invariant,
   automatically use a saved task-local Pillow compositor that preserves the
   canonical string and prove the rendered line structure. Never silently
   normalize supplied copy.
6. Inspect the final PNG at native and destination-preview sizes. Read every
   caption back and verify field placement, contrast, outline, safe area, joke
   fit, dimensions, and format.
</Procedure>

<Verification>
- Caption characters and field order match the saved canonical copy; required
  line breaks and whitespace are proven when marked invariant.
- Template identity/source and selection rationale are recorded. Third-party
  commercial usage rights remain unconfirmed and are never inferred.
- Content is not hateful, abusive, or personally targeted.
- Attach only the final requested PNG. Keep template provenance, caption spec,
  generation tally, and QA evidence in the pipeline report unless requested as
  deliverable sidecars.
</Verification>
