# Asset set — decomposition archetype

A consistent multi-asset set or batch: banner sets, illustration
series, icon rows, multi-page art, voice-line sets. The planning
problem is **consistency at batch cost** — locked once, produced
many.

## Decompose

1. **Anchor unit first** — 1–2 cheap samples per the family leaf's
   anchor kind (style block, palette, seed, voice params). Check it
   against your QA, show the user when taste is theirs to judge,
   and approve BEFORE any batch spend. Never let a batch run before
   its anchor passed — this gate is also what makes a batch
   card-eligible.
2. **Batch part(s)** — the set from the locked anchor with a
   complete per-item spec list (subjects, per-item dimensions/
   crops). Mass-parallel independent items ride the
   `anchored-image-batch` card (approved anchor + per-item specs +
   `Budget:` in the body); everything else stays resident.
3. **Revision rounds** target named items only — the anchor and
   unnamed items are preserved; a wholesale direction change
   re-anchors (new sample + sign-off) before any full re-render.

## Expected decomposition (your inspection standard)

Anchor unit (family, allowance) → batch unit(s) (count, per-item
specs, Budget) — plus, for cross-family sets (illustrated article:
images + captions), the parts split per `composite-media.md`.

## Pitfalls

- Batch before anchor approval — the classic budget burn; also
  anchor exploration on a card (cards require an APPROVED anchor as
  input).
- A "set" whose items have no shared anchor definition — that is N
  independent Part units, cheaper planned as such.
- Adaptive per-item drift (fresh seeds, paraphrased prompts,
  re-quantized palettes) — the anchor is reused verbatim; drift is
  a defect, not variety.
- Fixing per-item specs after release — the card body carries the
  COMPLETE list; an incomplete list is resident work.
