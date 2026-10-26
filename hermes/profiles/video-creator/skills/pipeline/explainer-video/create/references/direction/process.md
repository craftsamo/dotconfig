# Process

Intent: walk through a sequence of stages over time, where the order and
the running total matter as much as any single step.

Layout: a persistent progress indicator (a numbered stage tracker, a
simple stepped timeline, or stage labels that accumulate on screen) paired
with one focused view per unit for that stage's action. Each unit's
`before`/`after` should read as a visible state change on the tracker, not
only in the narration.

Affordance: the current stage is visually promoted (size, color or
position) while completed stages recede but stay legible, so a viewer who
glances away briefly can still tell where they are in the sequence. Avoid
resetting or hiding earlier stages — the accumulation is the point.

A custom direction may use a different tracker metaphor (a filling
container, a growing path) but must keep stage order and count legible
throughout. Works with any theme/style; pairs well with `worked-example`
when one stage needs a concrete instance.

QA: confirm the tracker's before/after state change is visible in the
sampled frames for the corresponding unit, and earlier stages stay legible
rather than reset across the sequence.
