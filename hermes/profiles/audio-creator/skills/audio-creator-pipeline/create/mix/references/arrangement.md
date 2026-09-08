# Mix spec v1 - exact schema

This is the authoritative shape `mix-media.py propose`/`render` enforce.
Author `<deliver>/spec.json` to this exactly - every field listed as
required below must be present, and no other top-level or cue key is
accepted.

## Top level

| key | required | type/range |
| --- | --- | --- |
| `version` | yes | integer, must be `1` |
| `what_for` | yes | nonblank text, <=8000 chars |
| `direction` | yes | nonblank text, <=8000 chars |
| `duration_seconds` | yes | number, `1..600` |
| `channels` | yes | integer, `1` or `2` |
| `target_lufs` | yes | `null`, or number `-70..-5` - always present, `null` is a valid explicit "no normalization" choice, never omit the key |
| `true_peak_dbtp` | yes | number `-9..-0.1` (never `null`); recommend `-1` absent a reason otherwise |
| `sources` | yes | array, `1..16` entries (see below) |
| `cues` | yes | array, `1..32` entries (see below) |
| `must_keep` | no | nonblank text, <=8000 chars |
| `timing` | no | string path to an exact timing-constraint JSON file (see below) |

## `sources[]` entries

Exactly `{id, path, role}`, plus optional `words` - no other keys, no `slug`.

| key | required | type/range |
| --- | --- | --- |
| `id` | yes | slug: 1-80 lowercase ASCII letters/digits, hyphen-separated; unique across sources |
| `path` | yes | text, <=4096 chars - the ORIGINAL local audio file's path |
| `role` | yes | one of `speech`, `music`, `sfx`, `other` |
| `words` | only on `role: speech` | text, <=4096 chars - local path to that source's own `.words.json` sidecar |

Every declared source must be referenced by at least one cue - an
unused source is refused. At propose time the helper freezes each
source's bytes into the bundle as `sources/<id>.audio` (and
`sources/<id>.words.json` for a `words` sidecar), rewriting the spec's
own `path`/`words` fields to those canonical bundle-relative names as
part of freezing. Your authored `spec.json` always names the real
external file; only the delivered `mix.json` carries the frozen names.

## `cues[]` entries

Exactly `{id, source, start, source_start, duration, gain_db, fade_in,
fade_out, envelope}` - **all nine fields are required on every cue**,
including `gain_db: 0`, `fade_in: 0`, `fade_out: 0` and `envelope: []`
when there is genuinely nothing to set; there is no default for an
omitted field, so nothing may be left out.

| key | range |
| --- | --- |
| `id` | slug, unique across cues |
| `source` | must equal a declared source's `id` |
| `start` | number, `0..duration_seconds` - the cue's position on the MIX timeline |
| `source_start` | number, `0..600` - where inside the SOURCE's own decoded audio the cue begins |
| `duration` | number, `>0..duration_seconds`; also `start+duration <= duration_seconds` and `source_start+duration <= 600`, and the source must actually decode to at least `source_start+duration` |
| `gain_db` | number, `-60..24` - the cue's own flat gain |
| `fade_in` | number, `0..duration` - linear-amplitude fade at the cue's own start |
| `fade_out` | number, `0..duration` - linear-amplitude fade at the cue's own end |
| `envelope` | array, `0..64` points |

`envelope` points are `{at, gain_db}`: `at` is `0..duration`, `gain_db`
is `-60..24`. An **empty** envelope (`[]`) is the normal way to say
"flat" - it is valid and common, not an omission. A **nonempty**
envelope must have at least 2 points, its first point's `at` must equal
exactly `0` and its last point's `at` must equal exactly the cue's own
`duration` (not "close to" - exact), and successive `at` values must
keep increasing once quantized to 48 kHz samples. The applied gain at
each sample is the cue's `gain_db` plus the envelope's linearly-
interpolated dB (0 dB when the envelope is empty), converted to linear
amplitude, then multiplied by the `fade_in`/`fade_out` linear-amplitude
ramps.

## Timing constraint file (optional, `timing`)

A separate local JSON file, referenced by the spec's `timing` field.
Required keys exactly `{version, duration_seconds, cues}` - no optional
keys.

| key | range |
| --- | --- |
| `version` | integer, must be `1` |
| `duration_seconds` | number `1..600`, must equal the spec's own `duration_seconds` exactly |
| `cues` | array, `1..32` entries, each exactly `{id, source, start, source_start, duration}` |

A `timing` cue does not have to name every spec cue - only the ones a
video edit constrains. But whichever ids it does name must already
match the spec's cue with that id EXACTLY on `source`/`start`/
`source_start`/`duration`: `propose` and `render` both validate this
themselves and refuse a mismatch rather than adjusting anything for
fit. Compose the spec first so its named cues already equal `timing`,
never the reverse.

## Other bounds

- The sum of every cue's `duration` (in 48 kHz samples) may not exceed
  256,000,000 sample-frames of DSP work.
- Seconds-to-sample quantization always rounds to the nearest sample,
  ties to even (48 kHz).

## Concrete valid example

`spec.json` for a 20-second settings-menu intro (VO leads, a music bed
ducks under it and swells back, one UI tick accent) - all three sources
used, `must_keep`/`timing` omitted since neither is needed here:

```json
{
  "version": 1,
  "what_for": "Settings menu intro: VO over a soft music bed with a UI tick accent",
  "direction": "VO leads 1s-9s; music bed under the whole mix, ducked under the VO and swelling back after; one UI tick accents the toggle mention at 4s",
  "duration_seconds": 20,
  "channels": 2,
  "target_lufs": -16,
  "true_peak_dbtp": -1,
  "sources": [
    {"id": "vo-toggle", "path": "/Users/agent/Workspaces/.deliverables/job-42/speech/vo_toggle.wav", "role": "speech", "words": "/Users/agent/Workspaces/.deliverables/job-42/speech/vo_toggle.words.json"},
    {"id": "bed", "path": "/Users/agent/Workspaces/.deliverables/job-42/music/bed_warm.wav", "role": "music"},
    {"id": "tick", "path": "/Users/agent/Workspaces/.deliverables/job-42/sfx/ui_tick.wav", "role": "sfx"}
  ],
  "cues": [
    {"id": "vo", "source": "vo-toggle", "start": 1, "source_start": 0, "duration": 8,
     "gain_db": 0, "fade_in": 0.1, "fade_out": 0.3, "envelope": []},
    {"id": "bed-cue", "source": "bed", "start": 0, "source_start": 0, "duration": 20,
     "gain_db": -6, "fade_in": 0.5, "fade_out": 1.5,
     "envelope": [
       {"at": 0, "gain_db": 0},
       {"at": 1, "gain_db": -8},
       {"at": 9, "gain_db": -8},
       {"at": 10, "gain_db": 0},
       {"at": 20, "gain_db": 0}
     ]},
    {"id": "tick-cue", "source": "tick", "start": 4, "source_start": 0, "duration": 0.4,
     "gain_db": -3, "fade_in": 0, "fade_out": 0, "envelope": []}
  ]
}
```

`bed-cue`'s envelope ducks the bed to -8 dB (on top of its own -6 dB
`gain_db`) across the VO window (1s-9s) and returns to 0 dB by 10s -
first point at exactly `0`, last point at exactly `20` (the cue's own
`duration`), five strictly increasing points.

A matching `timing.json` constraining only the VO cue's placement:

```json
{
  "version": 1,
  "duration_seconds": 20,
  "cues": [
    {"id": "vo", "source": "vo-toggle", "start": 1, "source_start": 0, "duration": 8}
  ]
}
```

## Authoring guidance (no exact `arrangement` supplied)

- Identify each source's `role` before placing anything. Speech
  normally anchors the timeline: place spoken cues first, at the
  client's stated pacing, then layer music/sfx around them.
- A music/sfx cue under speech usually needs its own level dropped
  (an `envelope` dip, as above) during the speech interval so the
  speech stays intelligible - state the chosen ducking depth explicitly
  in `description.md`.
- `arrangement`, when supplied as a file, is copied into the authored
  cues verbatim, per cue - never smoothed, retimed or reinterpreted. A
  control the schema does not accept (an out-of-range gain/envelope
  value, a cue referencing a nonexistent `source`, a cue outside
  `duration_seconds`) is a `Q<n>` back to the client, never silently
  clamped into range.
