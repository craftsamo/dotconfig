# Steady

Intent: a consistent arrangement from start to end - similar instrument
density, dynamics and rhythmic pattern throughout. The default when no
`direction` is given for a short BGM bed or loop-friendly cue.

Score guidance: keep track count and rough note density comparable across
the whole `duration_seconds`; avoid introducing a new track partway
through or dropping one out, except for the ending's own release (see
`ending`). Tempo (`bpm`) stays constant for the whole score - steady is an
arrangement/density choice, not a permission to change tempo mid-piece.

QA cue: compare note density and active track count in the first third
against the last third of the score; a steady score that quietly builds
or thins out is a `gradual-build`/mismatch to flag, not a passing steady
cue. A steady score can still end distinctly per `ending`.
