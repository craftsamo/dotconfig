# Steady

Intent: a consistent arrangement from start to end - similar instrument
density, dynamics and pattern throughout. The default when no `direction`
is given for a short BGM bed or loop-friendly cue.

Prompt guidance: describe a consistent texture for the whole duration
("steady/consistent throughout") rather than layering in "building"
language. Tempo language stays constant for the whole prompt - steady is
an arrangement choice, not a tempo instruction, and the model is not
guaranteed to honor an internal tempo change from prose alone.

QA cue: a returned piece that noticeably thins out or builds is a
possible `gradual-build`-shaped result rather than steady; note that
mismatch in QA rather than silently accepting it. A steady piece can
still have a distinct `ending`.
