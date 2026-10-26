# Fade

Intent: the piece thins out and quiets toward the end rather than landing
on a defined final note. Suits background beds that need to recede rather
than announce their end.

Prompt guidance: describe the fade in words ("gradually thins out and
quiets toward the end") - the model is not guaranteed to render an exact
output-level fade curve from prose. A guaranteed sample-accurate fade is
available separately as an `edit-music` `fade_out_ms` on the rendered
file if a harder guarantee is needed; do not claim the raw generated take
already fades cleanly without checking it.

QA cue: report requested `ending: fade` separately from whether the raw
render's tail actually measures quieter (available from level
measurement); recommend `edit-music fade_out_ms` when the raw tail does
not already recede.
