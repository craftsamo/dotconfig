# Plan mode — lock the direction before an expensive batch

Loaded when <ModeRouting> detects a plan task. For a consistent multi-asset
set or a costly single asset, fix the style + structure and get the
orchestrator's sign-off on a CHEAP sample BEFORE spending the full batch
budget — the media analog of a plan-before-build gate. The kernel's
<CommentProtocol> and <Budget> apply throughout; re-entry follows
`references/resume.md`, verification `references/verify.md` (plan anchor
profile), delivery `references/delivery.md`.

## When plan applies (else go straight to Produce)

- A **multi-asset set / batch** that must look consistent across items.
- A **single high-cost asset** (long video render) where a wrong direction is
  expensive to redo.
- The body opens with `Plan —`, or its `Review:` line asks to sign off the
  direction.

Skip plan — produce directly — for one cheap asset, or when the brief already
pins an exact reference the batch must match (there is nothing left to lock).

## Rules

- **Cheap first.** The only spend here is the style anchor: 1-2 low-cost
  samples (<Budget> "Plan-mode style anchor"). NEVER render the batch before
  the anchor is approved.
- **One anchor, reused.** The approved sample fixes the style; every batch
  asset then reuses that same anchor so the set stays consistent (see
  AnchorByType below).
- **Assume structure, block on taste.** Draft the asset/shot list yourself;
  block only for the creative-direction decision the sample settles.

## Procedure

0. **Preflight the capability.** Validate `references/brief.md`, load
   `references/capabilities.md`, load the selected leaf or preflight the
   core/external route, and write its capability handshake before making an
   anchor. Plan mode spends too; it never bypasses the production gate.
1. **Draft the plan** (no spend). Two parts, both reusable:
   - **Style spec** — the detailed, reusable description every asset shares:
     the prompt skeleton, palette, mood, composition rules, tokens. This is
     the anchor's text form.
   - **Structure** — the asset list with a one-line brief per item, or a
     scene/shot breakdown for video.
   `kanban_attach` the plan so it survives a respawn.
2. **Make the anchor** (small spend). Generate 1-2 samples from the style spec
   — the cheapest form that shows the look (one representative asset, low
   variant count). Record the tally in the `STATE:` comment
   (`spend: anchor 1/2`).
3. **Block for sign-off.** `STATE:` (plan pointer + spend tally), then a
   `Q<n>:` presenting the sample(s) and style spec — options = `approve` /
   `adjust — <knobs>`, recommendation marked; attach the samples.
   `kanban_block(kind=needs_input, reason="Q<n>: style anchor — <one line>")`.
   If the body says `Review: required`, run the full Review gate instead
   (`references/delivery.md` <ReviewGate>): attach the samples first, then
   block with a `REVIEW:` headline — the approval arrives as
   `DECISION(REVIEW): approved / changes`, not as a `DECISION(Q<n>)`. Stop
   after the block.
4. **On approval** (respawn: `DECISION(Q<n>): approve` — or
   `DECISION(REVIEW): approved` on a Review-gated card). The style spec is now LOCKED.
   Continue into Produce (`references/produce.md`): batch-generate every
   asset reusing the anchor (AnchorByType below), verify each against the
   approved sample (`references/verify.md`, batch profile), deliver per
   `references/delivery.md`. The plan attachment + locked spec are the
   durable contract — do not re-derive them.
5. **On `adjust`.** Apply the named changes, re-sample within the plan-spend
   allowance (a re-sample is one cheap gen, never the batch), then a fresh
   sign-off round.

## AnchorByType — how the locked style rides into every batch asset

| Asset | Anchor carried into the batch |
| --- | --- |
| still image | the **locked style prompt** (text) reused verbatim, subject swapped — the image tool takes no seed/reference, so consistency IS the shared prompt; tighten that prompt before re-sampling if it drifts |
| pixel-art | the **locked palette** — one named palette on every run, or a sample-derived palette applied by the loaded `creator-pixel-art` technic; never adapt per asset |
| video | the approved sample as `reference_image_urls` + a **fixed `seed`** on every render (both supported by `video_gen`) |
| p5.js / HTML motion | the approved design file + hero frame, with the same palette/type/motion tokens and deterministic seed/timeline contract |
| generated audio / music | the approved prompt, model/version, conditioning source, seed/sampling params, and short audio anchor |
| vocal song | the approved lyrics + structural/musical tags, model/version, sampling params, and short audio anchor |
| voice / narration | the same voice id and params across the set |

## Report

- The plan STEP delivers the attached plan + the approved sample(s); the
  Produce step then delivers the batch per `references/delivery.md`.
- After approval, a `PROGRESS:` comment names the locked anchor (palette name /
  seed / style-spec) so any respawn reuses it instead of re-deriving it.

## Pitfalls

- Rendering the batch before the anchor is approved — the exact spend this mode
  exists to prevent.
- Letting each asset drift: an adaptive palette, a fresh seed, or a paraphrased
  prompt instead of the ONE locked anchor.
- Spending past the plan allowance on samples — a wide exploration is a `Q<n>`
  with the cost stated, never a silent overrun.
- Treating plan as advisory (advisory ships nothing; plan spends a little to
  make the anchor) — or as produce (produce skips the sign-off gate).

## Verification

- No batch asset was generated before the anchor sign-off.
- Every delivered asset reuses the approved anchor (same prompt / palette /
  seed); a spot check against the sample confirms the set is consistent.
- Plan-spend stayed within the anchor allowance; any widening went through a
  `Q<n>` with its cost.
