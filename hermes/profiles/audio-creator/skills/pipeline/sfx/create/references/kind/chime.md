# chime

Three sine partials at `pitch`, `2*pitch` and `3*pitch`, each independently
decaying as `exp(-(3+harmonic)*t/seconds)/harmonic`: the fundamental decays
slowest and loudest, the octave and fifth-above-octave harmonics fade
faster and quieter, giving a bell/xylophone-like ring rather than a flat
tone.

- **Pitch** sets the fundamental note; 500-1200 Hz reads as a bell/chime,
  under 300 Hz reads as a low gong-like tone.
- **Duration** of 0.3-1.5s lets the harmonic decay actually register;
  under ~0.2s the ring is cut off before the harmonics separate audibly.
- No noise component — purely tonal, unlike click/ui-tick/noise-burst.
