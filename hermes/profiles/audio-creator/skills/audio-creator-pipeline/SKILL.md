---
name: audio-creator-pipeline
description: >-
  AudioCreator's spoken-audio and sfx hands. Load first for a filled
  generate-speech, edit-speech, analyze-speech, create-sfx, generate-sfx,
  edit-sfx or analyze-sfx form from Creator. Not music, singing, voice
  registration, script writing or video assembly.
version: 1.0.0
metadata:
  hermes:
    category: hands
    tags: [audio, speech, hands]
---

<Run>

1. Load the named `<verb>/<subject>/SKILL.md` (`speech` or `sfx`). Validate
   its form; missing or unusable fields return in one `Q<n>:` block. `no
   skill fits` is a finding, not permission to invent a workflow. An analyze
   form needs no `deliver`.
2. Read the approved script/source and previous delivery for `intent: revise`.
   Preserve words and voice identity for speech, the same closed kernel or
   engine and controls for sfx. Never substitute an engine, add acting beats,
   register voices, download models or repair the managed skill tree.
3. Run the leaf's Procedure. Speech leaves share `scripts/speech-media.py`;
   sfx leaves share `scripts/sfx-media.py` and generate-sfx's `sfx_engines`/
   `sfx_generate` tools (from a leaf: `../../scripts/<name>-media.py`), using
   the Hermes venv Python. Existing bundles are never overwritten.
4. Run the leaf's QA. Measurements, ASR and waveform stats are evidence, not
   listening. Preserve FAIL/WARN, estimated subtitle timing, unverified
   pronunciation/identity/performance and a short-clip's WARN-not-defect
   missing LUFS. A warning is not a reason for unlimited retakes or a
   generate-sfx re-roll.
5. Return the leaf's Report, durable paths and take/call tally. Speech is free
   of provider fees but limited to one take plus one corrective per script,
   including failed calls. Deterministic create/edit/analyze-sfx uses no model
   takes or provider fees. Generate-sfx defaults to the local Medium engine
   ($0 spend, seed-controlled, no loop/prompt_influence) within its attempt
   cap; only an explicitly chosen fal call spends against an approved cap and
   USD estimate. Reuse surviving audio after
   a packaging failure; do not synthesize again to fix a sidecar.

</Run>
