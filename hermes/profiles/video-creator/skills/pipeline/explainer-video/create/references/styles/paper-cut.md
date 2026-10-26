# Paper Cut

Intent: a warm, tactile, hand-made feel that softens a technical topic
without sacrificing readable shapes.

Material: layered die-cut paper shapes, each layer offset slightly from
the one behind it with a soft drop shadow implying real physical stacking.
Visible paper grain/fiber texture is subtle, never noisy enough to reduce
edge clarity on labeled parts.

Ink: solid, matte paper-color fills (no gradients within a single cut
shape); ink accents are additional cut/torn paper pieces, not drawn line
work — an "arrow" is a cut paper triangle, a "highlight" is a cut paper
underline shape. Shadow depth communicates layer order (foreground labels
sit visibly above the diagram, which sits above the backdrop).

Best paired with `comparison`/`misconception` directions, where distinct
paper layers can physically separate the two sides being contrasted. A
custom, equally concrete free-text style description is implemented
verbatim, never coerced onto this preset.

QA: confirm every accent (arrow, highlight) renders as a distinct cut-paper
shape rather than drawn line work, and that shadow depth still reads the
correct layer order in sampled frames.
