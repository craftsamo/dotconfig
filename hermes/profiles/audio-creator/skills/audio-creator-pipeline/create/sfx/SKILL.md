---
name: create-sfx
description: >-
  Deterministically synthesize one short SFX from a closed set of eight
  local waveform kernels (click, beep, chime, whoosh, riser, pop, ui-tick,
  noise-burst). No model, no network call, zero spend. A described
  real-world sound or anything outside these eight kernels routes to
  generate-sfx instead of an approximated kernel.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "sfx_<slug>.wav + .take.json"
    form:
      what_for:
        required: true
        label: "what the sound is for, in one sentence"
        example: "A UI confirm tick for a settings toggle"
      kind:
        required: true
        options: [click, beep, chime, whoosh, riser, pop, ui-tick, noise-burst]
        label: "one of the eight local kernels; see references/kind/<kind>.md for what it actually renders"
      seconds:
        required: true
        type: text
        label: "clip duration, 0.01 to 22 inclusive"
        example: "0.12"
      pitch:
        required: false
        type: text
        label: "carrier/cutoff frequency, 40-8000 Hz; default 880 if omitted"
        example: "1200"
      seed:
        required: false
        type: int
        label: "RNG seed for the kernel's noise component, 0-4294967295; default 0"
      slug:
        required: false
        label: "lowercase ASCII filename slug; default sfx"
      note:
        required: false
        type: text
---

<Procedure>

1. Confirm this is really a request for one of the eight closed local
   kernels, not a described real-world sound, music, speech or anything a
   kernel can only approximate. `no skill fits` for the latter is a
   finding for Creator (route to `generate-sfx`), never a kernel picked to
   stand in for something it does not render.
2. Read `references/kind/<kind>.md` for that kernel's actual waveform,
   what `pitch` does (some kernels ignore it or use it as a filter cutoff,
   not a note) and a sane duration range, before proposing `seconds`/
   `pitch` values. Do not guess numbers the kernel cannot express.
3. Run through the Hermes venv Python:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/sfx-media.py" synth --kind <kind> --seconds <seconds> --pitch <pitch> --seed <seed> --out <deliver>/take-01 --slug <slug>
   ```

   Do not use command substitution in executable paths; if `ghq root`
   differs on this machine, resolve it with a separate `ghq root` call
   first and then invoke the literal absolute Python path — never repeat
   the model generation to fix a packaging step. (Actual live failure:
   "Nested executable body could not be resolved.")

   Omit `--pitch`/`--seed` to use their defaults only when the form left
   them unset. Never call `image_generate`/`video_generate`/any model —
   this leaf is pure arithmetic synthesis with no network dependency.
4. `intent: revise`: rerun with the exact same `kind`/`seconds`/`pitch`/
   `seed` and a fresh `--out`; the decoded PCM is bit-identical on this
   numpy/ffmpeg install. Changing any control is a new sound, not a
   revision of the old one.

</Procedure>

<QA>

- Full decode, mono 48000 Hz PCM WAV, positive duration matching the
  requested `seconds`, no clipping; quote `measure.sample_peak_dbfs` and
  `clipping_count` from the `RESULT:` JSON.
- A short clip (<0.4s) legitimately reports `integrated_lufs: null` and
  status `WARN` — that is the documented short/ungated case, not a defect
  to chase with another take.
- Determinism is scoped to the decoded PCM hash on THIS numpy/ffmpeg
  install; never promise it holds across a different environment, and
  this leaf never produces a lossy derivative to compare against.
- No auditory verdict: `auditory_quality` stays `unverified` even on PASS.

</QA>

<Report>

Return `create-sfx` + kind/seconds/pitch/seed used, the delivered bundle
path, the `RESULT:` measurements and status, `spend: free`. Flag for
Creator only when the closed kernel set does not fit the actual ask.

</Report>
