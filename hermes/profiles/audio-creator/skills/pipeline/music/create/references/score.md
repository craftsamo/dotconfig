# Score schema (version 1)

AudioCreator authors this frozen score from the client's direction; the
client is never asked to write a score or a prompt themselves. A supplied
`score` file is only ever used when it already matches this schema
exactly - never coerced, patched or partially reused into a nonconforming
document.

```json
{
  "version": 1,
  "duration_seconds": 1..60,
  "bpm": 40..240,
  "meter": "4/4" | "3/4" | "6/8",
  "key": "non-empty text, e.g. C major, A minor",
  "seed": 0..4294967295,           // optional, default 0
  "tracks": [
    {
      "id": "ascii-slug",
      "instrument": "sine" | "triangle" | "pulse" | "fm-bell" | "noise",
      "gain_db": -60..0,           // optional, default -12
      "pan": -1..1,                // optional, default 0
      "notes": [
        {
          "pitch": 24..96,          // MIDI note number
          "start": ">= 0",          // quarter-note beats from bar 1 beat 1
          "duration": "> 0",        // quarter-note beats
          "velocity": 0..1          // optional, default 0.8
        }
      ]
    }
  ]
}
```

Hard bounds: at most 8 `tracks`, at most 2048 `notes` total across all
tracks, every note's `start + duration` must land fully inside
`duration_seconds` (no note may extend past the end). `start`/`duration`
are always counted in **quarter-note beats**, even under `meter: "6/8"` -
there is no separate eighth-note or dotted-quarter beat unit; convert a
6/8 feel (two dotted-quarter groups per bar) into quarter-note beat values
before writing `notes`.

No DAW project, MIDI file or notation PDF is produced or promised from
this schema - it drives a simple electronic waveform synthesizer
(`stable_audio3.py`'s score renderer), not a sampled/realistic
instrument library. A `chiptune` lead and a `minimal-electronic` lead
sound different only through instrument choice, note density and
register, never through a hidden "realistic instrument" toggle.

Determinism scope: the same score, the same renderer and the same
environment (numpy/ffmpeg install) reproduce byte-identical decoded PCM.
This does NOT mean two different free-text descriptions of "the same
piece" render identically, and it does not survive a different
renderer/environment - treat replay claims accordingly.

Worked example (valid, 96 BPM / 4-4 / 20s, 8 bars): `duration_seconds: 20`,
`bpm: 96`, `meter: "4/4"` gives 4 beats/bar at 0.625s/beat, so 8 bars span
32 beats = 20s exactly. A melody track's last note might start at beat 30
with `duration: 1.5` (ends at beat 31.5, i.e. ~19.7s) leaving a short
release before the 20s boundary - this is what `ending: resolve` requires
(see `references/ending/resolve.md`): the final note must finish with
margin before `duration_seconds`, not exactly flush against it.
