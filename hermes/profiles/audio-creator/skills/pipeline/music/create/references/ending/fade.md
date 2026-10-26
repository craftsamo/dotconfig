# Fade

Intent: the piece thins out and quiets toward the end rather than landing
on a defined final note. Suits background beds that need to recede rather
than announce their end.

Score guidance: this schema has no output-level fade envelope - express
fade through the score itself: drop tracks out one by one and/or lower
`velocity` on the remaining notes across the final bars, ending on a low-
velocity, sparse texture rather than a strong final chord. A true
sample-accurate audio fade-out is also available separately as an
`edit-music` `fade_out_ms` on the rendered file if a harder guarantee is
needed.

QA cue: compare active track count and average `velocity` in the closing
bars against the body of the piece; a fade ending that still lands loud
and full is a mismatch to flag before approval.
