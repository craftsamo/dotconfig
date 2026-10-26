# Tense

Mood: uneasy, anticipatory, unresolved; suits a suspense/waiting bed or a
buildup underscore, not a resolved or celebratory cue.

Waveform palette: pulse/sine for a low, repeating pedal or ostinato figure,
dissonant or close-interval fm-bell/triangle accents used sparingly,
noise for a low sustained rumble/texture bed. Favor a repeated short
rhythmic cell over a flowing melody, and close/dissonant intervals over
consonant ones.

Not fixed: tense implies no forced tempo or key. `theme_detail`,
`direction` and `tempo` override any default implied here; a slow tense
cue (dread) and a fast tense cue (panic) are both valid.

Adaptation example: a tense waiting-room cue might repeat a two-note
pedal figure under a low noise bed with no melodic resolution by the end;
a tense chase-adjacent cue keeps the repeated cell but raises tempo and
note density instead of abandoning the ostinato.

QA cue: verify the score actually withholds resolution (does not land on
a clearly consonant final chord/note unless `ending: resolve` was also
requested) and uses a repeating figure rather than a freely wandering
melody; a fully resolved, consonant score mislabeled `tense` is a
mismatch to flag before approval.
