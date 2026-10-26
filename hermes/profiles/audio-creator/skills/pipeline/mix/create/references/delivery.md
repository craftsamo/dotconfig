# Delivery contract

A completed `create-mix`/`edit-mix` bundle under `<deliver>/take-NN/`
contains:

- `mix_<slug>.wav` - the rendered 48 kHz PCM16 master, mono or stereo
  per the approved `channels`.
- `mix.json` - the frozen, approved spec exactly as validated (this is
  the delivered artifact; `spec.json` is only the local `--spec-file`
  authoring input's own filename and never appears in the bundle),
  with every source's `path`/`words` rewritten to its canonical
  `sources/<id>.audio` / `sources/<id>.words.json` bundle-relative name.
- `mix.take.json` - the measured take evidence: `output_policy`
  (the approved `target_lufs`/`true_peak_dbtp`), actual measured
  duration/peak/true-peak/clipping/integrated LUFS, per-source
  `source_measures` (native decode facts, channel-conversion method,
  and a stereo-to-mono fold's `mono_fold_energy_delta_db`),
  `normalization` evidence (see below), and status (PASS/WARN/FAIL).
- `proposal.md` (carried over from the approved `proposal-v<N>/`) and
  `sources/` - byte-frozen copies of every input file the approved spec
  used, verified by hash before render.
- `timing.json` - only present when `timing` was supplied in the form;
  the exact constraint it applied.
- `captions.json` + `mix_<slug>.srt` - only present when at least one
  spoken cue's source carried a `.words.json` sidecar. Captions are
  `kind: mix-captions`, `version: 1`, `estimated: true` always; each
  caption/word/segment interval is the sidecar's own timing transformed
  to mix time - never a fresh ASR pass over the rendered master. A cue
  whose source has no sidecar contributes no captions for that
  interval, disclosed rather than filled in as an estimate presented as
  measured.

## Words sidecar contract (for a `role: speech` source's `words`)

The sidecar (as produced by generate-speech/edit-speech) must contain
`file` (the source audio's ORIGINAL filename, not its frozen `<id>.audio`
name), `duration` (within 0.15s of the source's actual decoded
duration), `pcm_sha256` (a hash of a specific mono 48 kHz PCM extraction
of the source), and three list fields `words`/`captions`/`segments`
(each bounded, `segments` may be empty but must exist). A cue's own trim
crossing a word/caption/segment boundary in that sidecar is refused
before any file is written. Once ANY source in the mix carries a
sidecar, no two speech-role cues may overlap on the mix timeline at
all - even a speech cue with no sidecar of its own - the helper refuses
that too, not just an overlap between two captioned cues.

## Normalization (when `target_lufs` is not `null`)

A single ffmpeg `loudnorm` MEASUREMENT pass (not a two-pass loudnorm
application) determines the gain needed to hit `target_lufs`, then that
one constant scalar gain is applied directly to the summed mix - never
ffmpeg's own dynamic-loudnorm/limiter path, so the approved envelopes'
relative shape is preserved exactly. If that single gain would push the
true peak past the approved `true_peak_dbtp` ceiling, the render is
FAIL ("constant gain cannot meet both loudness and true-peak targets;
revise the proposal") - never a silently applied limiter. Ask for a
revised `target_lufs`/cue gains in a new proposal instead of retrying
the same one.

## Channel conversion

Mono source into a stereo mix: duplicated at unity gain on both
channels. Stereo source into a mono mix: arithmetic mean of the two
channels; if that fold loses more than 6 dB of signal energy (possible
phase cancellation), `mono_fold_energy_delta_db` in `source_measures`
carries a disclosed WARN - not a FAIL, and not a listening claim.
Seconds-to-sample positions always round to the nearest sample, ties to
even, at 48 kHz.

No file in this bundle is ever produced by a fresh network call, an ASR
pass on the mixed master, source separation, or a loop/time-stretch/
pitch operation - the helper only decodes, places, gains, fades and
sums already-existing PCM, then applies the one approved normalization
gain when requested.
