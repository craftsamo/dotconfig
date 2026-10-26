# whoosh

White noise run through a one-pole low-pass filter whose cutoff is set by
`pitch` (`alpha = 1 - exp(-2*pi*pitch/48000)`), then shaped by a
`sin(pi*u)^2` swell that rises to a peak at the clip's midpoint and falls
back to zero at both ends — an air/wind swell, not a decaying transient.

- **Pitch** here is a low-pass cutoff, not a musical note: low values
  (60-300 Hz) sound like a dull, muffled rush; high values (1000-4000 Hz)
  sound closer to hiss/wind. There is no audible discrete tone.
- **Duration** of 0.3-2s lets the rise-and-fall swell register; very
  short durations (<0.15s) collapse the swell into a soft noise blip.
- The only kind whose filter state is generated sample-by-sample
  (a running IIR, not a closed-form envelope).
