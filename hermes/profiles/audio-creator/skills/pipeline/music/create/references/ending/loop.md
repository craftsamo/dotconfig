# Loop

Intent: the delivered file is meant to be repeated seamlessly by a
downstream player. `ending: loop` is a request for the composed material
to end on a point compatible with looping (matching or complementary
harmony/rhythm at the seam) - it is **not** a promise that this leaf's
render itself loops, and it is not a backend "make it loop" flag.

Score guidance: write the final bar so it resolves rhythmically/
harmonically back toward the piece's opening bar (same or compatible
`key`, similar rhythmic position on beat 1) so a downstream repeat reads
as continuous rather than jarring. Do not schedule a hard cutoff mid-
phrase.

Actual loop delivery: producing a verified seam is a separate, explicit
`edit-music` step (`loop_seconds`, `crossfade_ms`) on the rendered WAV,
with only a numerical boundary-sample check as evidence - never a
musical "sounds seamless" claim from this leaf alone.

QA cue: confirm the score's own note-writing supports a clean loop point
(no note left hanging mid-duration at the boundary) and that the report
names the separate edit-music step as still required for an actual
looping delivery, rather than claiming the composed score alone loops.
