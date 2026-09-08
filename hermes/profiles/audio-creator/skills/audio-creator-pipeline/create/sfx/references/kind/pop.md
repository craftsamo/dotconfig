# pop

`sin(2*pi*pitch*(t - 0.4*t*u))` multiplied by `exp(-9*t/seconds)`: the
`-0.4*t*u` term makes the instantaneous frequency fall across the clip (a
downward chirp) while the amplitude decays more slowly than `click`
(`exp(-9...)` vs `click`'s `exp(-28...)`), giving a rounder "pop"/bubble
transient instead of a hard click.

- **Pitch** sets the starting frequency of the downward chirp; 300-900 Hz
  reads as a bubble/cork pop, lower values read as a soft thump.
- **Duration** of 0.05-0.3s is enough for the pitch-drop and decay to be
  audible; longer values just extend inaudible tail silence.
- No noise component, unlike click/ui-tick/noise-burst — the character
  comes entirely from the falling pitch plus the slower decay.
