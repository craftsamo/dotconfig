# Direction route - lock the style before an execute batch

This reference is loaded only under top-level `Mode: execute` when the
internal route is `Direction`. It is the existing style-anchor execution gate,
not the PlanningGraph specialist branch. Top-level `Mode: plan` must not load
this file and must never spend on a style anchor.

## When Direction applies

- A multi-asset set or batch must look consistent across items.
- A single high-cost asset, such as a long video render, needs a direction
  check before production.
- The execute task opens with `Plan -`, or its `Review:` line asks for a
  direction sign-off.

Skip Direction and enter execute Produce directly for one cheap asset or an
exact-reference batch that has no remaining style decision.

## Rules

- The only Direction spend is 1-2 cheap style-anchor samples within the
  execute Budget. Never render the full batch before approval.
- One approved anchor is reused by every asset in the batch.
- Draft the asset or shot structure yourself. Block only on the creative
  direction that the anchor settles.

## Procedure

0. Preflight `references/brief.md`, `references/capabilities.md`, and the
   selected canonical leaf or core/external route. Write the capability
   handshake before making an anchor. Direction is allowed to spend; top-level
   Mode plan is not.
1. Draft the reusable plan without spend:
   - Style spec: prompt skeleton, palette, mood, composition rules, and
     reusable tokens.
   - Structure: one-line asset list or a scene/shot breakdown.
   Attach the plan so it survives a respawn.
2. Generate 1-2 cheap samples from the style spec. Record the tally in
   `STATE:` as `spend: anchor 1/2`.
3. Checkpoint and block for sign-off with `Q<n>:` and the samples attached.
   Offer `approve` or `adjust - <knobs>` and mark a recommendation. Use the
   `REVIEW:` gate instead when the execute task explicitly requires Review.
4. After approval, the style spec is locked. Continue into execute Produce,
   reuse the anchor, verify every asset, and deliver through
   `references/delivery.md`.
5. On `adjust`, apply the named changes and re-sample within the Direction
   allowance. A re-sample is one cheap generation, never the full batch.

## AnchorByType

| Asset | Anchor carried into execute Produce |
| --- | --- |
| still image | locked style prompt reused verbatim with the subject swapped |
| pixel-art | one locked named or sample-derived palette |
| video | approved sample as reference image URLs and a fixed seed |
| p5.js / HTML motion | approved design file, hero frame, palette, type, motion tokens, and deterministic timeline |
| generated audio / music | approved prompt, model/version, conditioning, seed, sampling parameters, and short audio anchor |
| vocal song | approved lyrics, structural tags, model/version, sampling parameters, and short audio anchor |
| voice / narration | the same voice id and parameters across the set |

## Report

- The Direction stage delivers the attached plan and approved samples. Execute
  Produce then delivers the batch through `references/delivery.md`.
- After approval, `PROGRESS:` names the locked anchor so a respawn does not
  re-derive it.

## Pitfalls

- Rendering the batch before the Direction anchor is approved.
- Letting assets drift through an adaptive palette, fresh seed, or paraphrased
  prompt instead of the one locked anchor.
- Spending past the Direction allowance without a `Q<n>:` cost request.
- Treating this execute route as a specialist plan, or treating top-level
  `Mode: plan` as permission to make an anchor.

## Verification

- No batch asset was generated before the Direction anchor sign-off.
- Every delivered asset reuses the approved anchor and passes a consistency
  spot check against the sample.
- Direction spend stayed within its execute anchor allowance; widening used a
  `Q<n>:` block and an explicit grant.
