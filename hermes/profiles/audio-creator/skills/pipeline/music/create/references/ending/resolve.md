# Resolve

Intent: land clearly on a consonant final note/chord and let it ring or
release naturally within the score's own duration - a "finished" feeling
close. Suits an opener/closer or any cue that should not feel cut off.

Score guidance: the final notes across the active tracks should land on
consonant pitches relative to `key`, with their `start + duration` ending
at or before `duration_seconds` (a resolve needs its own release time
inside the total duration - do not schedule the final note to end exactly
at the duration boundary with no tail; leave a short release window).

QA cue: check the last notes per track for consonance with `key` and
confirm the final note's `start + duration` finishes with some margin
before `duration_seconds`, not flush against it - a resolve that gets cut
off by the duration boundary is a mismatch to flag before approval.
