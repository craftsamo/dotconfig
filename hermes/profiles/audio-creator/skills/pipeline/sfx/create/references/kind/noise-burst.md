# noise-burst

White noise shaped only by `sin(pi*u)^2` (a smooth rise-and-fall bump
across the whole clip, peaking at the midpoint) — no tonal component and
no exponential decay, so `pitch` has no audible effect on this kind.

- **Pitch** is accepted by the form but does not change this kind's
  signal; do not describe a noise-burst request in terms of a pitch/note.
- **Duration** of 0.05-0.5s gives a short broadband burst (static, wind
  gust, impact texture); longer values read as a slow noise swell more
  than a "burst".
- Distinct from `whoosh`: `whoosh` is filtered (band-limited) noise with a
  pitch-controlled cutoff; `noise-burst` is unfiltered full-band noise.
