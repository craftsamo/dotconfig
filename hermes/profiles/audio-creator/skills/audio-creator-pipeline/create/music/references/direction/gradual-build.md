# Gradual build

Intent: add parts and/or density over the course of the piece - more
tracks active, more notes per bar, or higher velocity as it progresses.
This is an arrangement/density change, **not** an automatic tempo
increase; `bpm` stays constant across the score unless `tempo` explicitly
asks for a change (which this schema's fixed `bpm` cannot express within
one score - flag that as a scope gap rather than faking it with note
timing tricks).

Score guidance: start with fewer active tracks/lower velocity and
increase track count and/or note density across later bars. A build that
never actually adds a track or increases density, and instead only gets
louder via `gain_db`, does not satisfy this direction on its own.

QA cue: compare active track count and note density in the opening bars
against the closing bars of the body (before any `ending` release); the
later section must show measurably more activity. A flat-density score
mislabeled `gradual-build` is a mismatch to flag before approval.
