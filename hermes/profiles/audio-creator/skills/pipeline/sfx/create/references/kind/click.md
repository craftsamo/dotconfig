# click

`sin(2*pi*pitch*t)` mixed with heavy white noise (0.7 of amplitude), the
mix multiplied by `exp(-28*t/seconds)`: a fast exponential decay envelope
that reaches roughly 1/e in about 1/28 of the requested duration. Above
~0.15-0.2s of the tail the signal is already below -60 dBFS and reads as
silence, not a longer click.

- **Pitch** sets the faint tonal component under the noise; 800-2000 Hz
  reads as a hard mechanical click, under 300 Hz reads as a dull thud.
  Noise dominates perception far more than pitch here.
- **Duration** should stay short (0.02-0.15s) — a long `seconds` value
  just adds inaudible silence after the decay, not a longer click.
- Distinct from `ui-tick`: same decay shape, but click's 0.7 noise mix is
  far grittier/louder than ui-tick's 0.12.
