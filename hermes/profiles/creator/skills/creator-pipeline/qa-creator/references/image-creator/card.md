# Quality assurance — image-creator: card

Read [common quality assurance](../../SKILL.md) first.

For Card compare exact copy, selected look, layout at the actual destination
and readable reduced-size previews. Tiled output has main title/brand/meta on
tile 1 and independent headings inside their own tiles; backgrounds may cross
seams, text must not. Explicit authored copy_blocks can add text or repeated
branding to other tiles; check the requested presence/order, not template parity.
Measured bounds/stable snapshots and lossless PNG tile
reassembly prove geometry, not contrast/readability or platform crop behavior.
Keep the pair's candidate status and LOCAL SIMULATION gap label visible in
delivery; X article verifies only the user-observed 5:2 recommendation, not
official pixel dimensions. Analyze-card returns measurements and bounded
visual findings, not repaired media. Reject protected-content crop loss or
surface it, never silently accept a dimension-correct but unusable edit.

For authored layouts, confirm frozen source/hash evidence and check the
requested placement and typography against the use-size preview. The hands
report font sizes without automatic shrinking; those numbers are not a
readability verdict. Complex masks, painted occlusion, contrast and glyph
coverage remain visual checks. Do not accept a smaller/relocated substitute
for a protected design because a technical check passed. A client-agent's
implementation decision is not evidence that the human changed that condition.

The look-before-you-answer numbered steps and the verdict/delivery shape are
common — see [common quality assurance](../../SKILL.md).
