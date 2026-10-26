# Contrast

Intent: a clear A/B (or A/B/A) shift in character partway through - a
change in instrumentation, register or energy, then usually a return or a
distinct close. Not a gradual ramp (`gradual-build`) and not one
consistent texture (`steady`).

Prompt guidance: describe both sections and the shift explicitly ("opens
with X, shifts to Y partway through, contrasting in [instrumentation /
register / energy]"). The model is not guaranteed to place the shift at
an exact time; treat any boundary as approximate, not frame-accurate.

QA cue: a follow-up analyze-music pass's boundary/energy-window
candidates are the closest available evidence for whether a shift
actually occurred; without that check, mark the contrast as requested but
unverified rather than assumed present.
