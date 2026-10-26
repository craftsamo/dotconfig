# riser

`sin(2*pi*pitch*(0.5*t + 0.75*t*u))` mixed with a small amount of noise
(0.25), the whole signal scaled by `u^1.5` (`u` runs 0 -> 1 across the
clip): both the instantaneous frequency and the amplitude climb from
quiet/low toward loud/high over the full duration — a build-up/tension
riser, the opposite envelope shape from the decaying kinds.

- **Pitch** sets where the sweep starts and how far it climbs (the
  instantaneous frequency multiplier runs from `0.5*pitch` toward
  `1.25*pitch`); 200-600 Hz gives a musical rising sweep, higher values
  read as a rising alarm/tension cue.
- **Duration** should be long enough to hear the climb, 0.5-3s; a very
  short riser barely differs from a short beep with noise.
- Unlike click/pop/chime, amplitude builds UP across the clip rather than
  decaying — do not expect a transient attack at the start.
