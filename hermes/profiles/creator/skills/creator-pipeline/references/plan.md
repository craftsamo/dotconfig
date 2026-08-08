# Direction route - produce the anchor unit

This reference is loaded when the internal route is `Direction`: the
released **anchor unit** — cheap samples that lock direction before the
batch or high-cost spend. The structure and style decisions arrive in the
unit's spec; you translate them into a reusable style spec and samples.
Approval of the anchor is the assistant's (and the user's, when taste is
theirs) — never yours.

## When Direction applies

- A multi-asset set or batch must look consistent across items.
- A single high-cost asset, such as a long video render, needs a direction
  check before production.
- The request opens with `Plan —`, or a high-cost/batch request has an
  unresolved direction choice.

Skip Direction and enter Produce directly for one cheap asset or an
exact-reference batch that has no remaining style decision.

## Rules

- The only Direction spend is 1-2 cheap style-anchor samples within the
  Direction Budget. Never render the full batch before approval.
- One approved anchor is reused by every asset in the batch.
- The asset/shot structure and the direction choices come from the
  released spec; turning them into a style spec (prompt skeleton,
  reusable tokens) is your craft. A structural choice the spec leaves
  open is a spec gap, not yours to draft.

## Runtime boundary

Direction is resident-session work by default. Anchor exploration is NOT a
kanban catalog unit: present the plan and samples in the session reply and
wait for approval there. A kanban card requires an already-approved anchor;
only then may it run the legal `anchored-image-batch` unit with settled inputs.

## Procedure

0. Preflight `references/brief.md`, `references/capabilities.md`, and the
   selected canonical leaf or core/external route. Write the capability
   handshake before making an anchor. Direction is allowed to spend; the
   top-level plan route is not.
1. Derive the reusable style spec without spend — prompt skeleton,
   palette, mood, composition rules, reusable tokens — from the released
   spec's decisions (the asset list / shot structure arrives decided).
   Present it in the resident-session reply; retain it with the job's
   durable files when later work will inherit it.
2. Generate 1-2 cheap samples from the style spec. Record the tally in the
   reply as `spend: anchor 1/2`.
3. Present the samples in the resident-session reply and wait for approval.
   Ask `Q<n>:` with `approve` or `adjust - <knobs>`, and mark a
   recommendation. Do not generate the full batch before approval.
4. After approval, the style spec is locked. Continue into Produce, reuse the
   anchor, verify every asset, and deliver through `references/delivery.md`.
5. On `adjust`, apply the named changes and re-sample within the Direction
   allowance. A re-sample is one cheap generation, never the full batch; ask
   again in the session reply.

## AnchorByType

| Asset | Anchor carried into Produce |
| --- | --- |
| still image | locked style prompt reused verbatim with the subject swapped |
| pixel-art | one locked named or sample-derived palette |
| video | approved sample as reference image URLs and a fixed seed |
| p5.js / HTML motion | approved design file, hero frame, palette, type, motion tokens, and deterministic timeline |
| generated audio / music | approved prompt, model/version, conditioning, seed, sampling parameters, and short audio anchor |
| vocal song | approved lyrics, structural tags, model/version, sampling parameters, and short audio anchor |
| voice / narration | the same voice id and parameters across the set |

## Report

- The Direction stage presents the plan and samples in the session reply.
  Produce then delivers the batch through `references/delivery.md`.
- After approval, the reply names the locked anchor so a later session or
  legal anchored-image-batch card does not re-derive it.

## Pitfalls

- Rendering the batch before the Direction anchor is approved.
- Letting assets drift through an adaptive palette, fresh seed, or paraphrased
  prompt instead of the one locked anchor.
- Spending past the Direction allowance without an approval question and
  explicit cost request.
- Treating an advisory request as permission to make an anchor.

## Verification

- No batch asset was generated before the Direction anchor approval.
- Every delivered asset reuses the approved anchor and passes a consistency
  spot check against the sample.
- Direction spend stayed within its anchor allowance; widening used a
  `Q<n>:` cost question in the reply and an explicit grant.
