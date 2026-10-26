# Gradual build

Intent: add instruments and/or energy over the course of the piece.
This is an arrangement/density instruction, **not** a tempo increase
instruction; do not add "speeding up" or BPM-change language to the
prompt for this direction.

Prompt guidance: describe a sparse opening that adds layers/density
toward the end ("starts sparse with just X, gradually adds Y and Z,
fuller by the end"). The model is not guaranteed to place the build at an
exact bar; treat the request as directional, not frame/bar-accurate.

QA cue: compare the estimated energy/spectral windows from a follow-up
analyze-music pass (if requested) in the opening versus closing portion;
a flat-energy result mislabeled `gradual-build` is a mismatch to flag,
not silently accepted as passing.
