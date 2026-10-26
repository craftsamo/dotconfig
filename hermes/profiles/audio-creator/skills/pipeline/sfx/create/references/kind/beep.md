# beep

`sin(2*pi*pitch*t)`, a pure sustained sine tone at `pitch` Hz held for the
entire `seconds` duration (only the shared attack/release edge fades it in
over the first 4% and out over the last 8% of the clip — there is no
internal decay).

- **Pitch** IS the beep: 440-1000 Hz reads as a familiar notification/UI
  tone; below ~150 Hz it reads as a hum rather than a beep.
- **Duration** should match the sustained note wanted (0.1-1s for a UI
  beep, longer for an alarm tone); unlike the transient kinds, a long
  `seconds` here is audibly a longer held tone, not silence.
- The only kind with zero noise and zero internal envelope shaping.
