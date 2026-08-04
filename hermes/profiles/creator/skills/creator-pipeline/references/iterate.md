# Iterate — revise an existing deliverable without starting over (engine)

Load this when the intent is **revise**: the card asks to fix, redo, or
version-up something a previous card (or a Review round) already delivered
— `v2`, «作り直し», «修正», feedback lists. Revise is NOT a fresh brief:
its raw material is the previous delivery, and its economics are "change
what the feedback invalidates, preserve everything already approved."

## Inheritance — first move, before any spend

Locate the previous version and pull its reuse contract:

1. The card body's Inputs must point at the source: the previous card id
   and/or its attachments. `kanban_show <previous id>` — read its
   DECISIONs (settled taste questions stay settled), its final report
   (anchor values: style spec, palette, seed + reference, voice params),
   and its attachments.
2. Missing provenance (no previous-card pointer, no anchor, "you know the
   one") → ONE `Q<n>` block asking for the source card/attachments. Never
   reconstruct a deliverable from memory or regenerate blind — that is how
   version chains drift.
3. Note the inherited anchor values in your first `STATE:`/`PROGRESS:`
   comment — the revise run is now accountable to them.

## FeedbackTriage — classify before touching anything

Itemize the feedback (body lines, `DECISION(REVIEW): changes — <list>`),
then classify EACH item — the class decides the cheapest correct move:

| Class | The item asks for | Move |
| --- | --- | --- |
| **tweak** | a parameter-level change (crop, duration, text fix, color nudge, one word of narration) | re-process or re-render the affected asset with the ONE knob changed; anchor untouched |
| **partial regen** | one asset / segment / scene is wrong, the rest approved | regenerate only that piece, reusing the locked anchor (same prompt skeleton / palette / seed / voice) |
| **direction change** | the look/concept itself is rejected (new style, different concept) | STOP - the anchor is invalid. This is execute Direction work: lock a NEW cheap anchor and get sign-off (`references/plan.md`) BEFORE any full re-render. Say so in a comment; if the card's Budget cannot carry an anchor round, block. |

Mixed feedback is normal: run tweaks and partial regens under the inherited
anchor; a single direction-change item freezes full-batch spend until the
new anchor is approved. **Never answer a direction change with a full
re-render at full cost** — that is the failure mode this file exists to
prevent (five-version card chains, each starting from scratch).

## PreserveApproved — the other half of the contract

Everything the feedback does NOT name is already approved and must survive
identically:

- Reuse, don't re-create: same seed/reference for untouched video assets,
  same palette file, the locked prompt verbatim (edit the one knob, never
  paraphrase — paraphrase is regeneration in disguise).
- Verify the preservation, not just the fix: side-by-side (previous vs
  new) per revised asset — the named items changed, the unnamed aspects
  didn't (`references/verify.md`, revise profile).

## Budget

A revise card carries its own `Budget:`; absent → the standard defaults
apply **per revised asset** (not per asset of the original set — untouched
assets cost nothing). Direction changes add an anchor allowance (1-2 cheap
samples) only via execute Direction sign-off or an explicit grant. The inherited
delivery is free; spending to re-make what could be reused is the overrun
to catch in V5.

## VersionTrail

- Name outputs as the next version (`…_v3.mp4`), never overwrite the
  inherited files in the workspace.
- `PROGRESS:` per revised asset: which feedback items it closes, tally.
- The final report maps feedback item → change made (or → declined, with
  the reason) and re-states the (possibly re-locked) anchor values for the
  NEXT revise card (`references/delivery.md`).

## Pitfalls

- Regenerating the whole set for a one-item feedback — triage first.
- Treating a direction change as a tweak: batch-rendering a new look
  without an approved anchor burns the budget the plan gate exists to
  protect.
- Paraphrasing the locked prompt "to include the feedback" — edit the
  named knob, keep the rest verbatim.
- Re-asking taste questions the previous card already settled (read its
  DECISIONs first).
- Fixing the named items while silently regressing approved aspects — the
  side-by-side exists for both directions.
- Starting work without the previous card's anchor because "the brief
  describes it well enough" — descriptions drift, anchors don't.

## Verification

- Inheritance ran before any spend: previous card read, anchor values
  noted in a comment.
- Every feedback item classified and mapped to a move; direction changes
  went through an anchor round, never straight to full re-render.
- `references/verify.md` revise profile passed (side-by-side both ways);
  spend stayed within the revise card's own Budget.
