# ui-tick

Same shape as `click` — `sin(2*pi*pitch*t)` mixed with white noise, both
decaying as `exp(-28*t/seconds)` — but with only 0.12 noise amplitude
(against click's 0.7), so the tonal `pitch` component dominates and the
result reads as a soft, unobtrusive UI tick rather than a gritty click.

- **Pitch** is clearly audible here (unlike `click`): 1000-3000 Hz gives a
  crisp, small UI tick; lower values sound duller and less "digital".
- **Duration** should stay very short, 0.01-0.08s — this kind is meant for
  rapid, repeatable UI feedback, not a standalone sound effect.
- Choose `ui-tick` over `click` whenever the ask is "subtle"/"soft"/
  "unobtrusive"; choose `click` for "hard"/"mechanical"/"loud".
