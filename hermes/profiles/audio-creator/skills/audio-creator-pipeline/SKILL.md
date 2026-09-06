---
name: audio-creator-pipeline
description: >-
  AudioCreator's spoken-audio hands. Load first for a filled generate-speech,
  edit-speech or analyze-speech form from Creator. Not music, singing, sound
  effects, voice registration, script writing or video assembly.
version: 1.0.0
metadata:
  hermes:
    category: hands
    tags: [audio, speech, hands]
---

<Run>

1. Load the named `<verb>/speech/SKILL.md`. Validate its form; missing or
   unusable fields return in one `Q<n>:` block. `no skill fits` is a finding,
   not permission to invent a workflow. An analyze form needs no `deliver`.
2. Read the approved script/source and previous delivery for `intent: revise`.
   Preserve words and voice identity. Never substitute an engine, add acting
   beats, register voices, download models or repair the managed skill tree.
3. Run the leaf's Procedure. Its shared helper is
   `scripts/speech-media.py` (from a leaf: `../../scripts/speech-media.py`),
   using the Hermes venv Python. Existing bundles are never overwritten.
4. Run the leaf's QA. Measurements and ASR are evidence, not listening.
   Preserve FAIL/WARN, estimated subtitle timing and unverified pronunciation,
   identity and performance. A warning is not a reason for unlimited retakes.
5. Return the leaf's Report, durable paths and take tally. Synthesis is free
   of provider fees on this profile, not unlimited: default one take plus one
   corrective per script, including failed synthesis calls. Reuse surviving
   audio after a packaging failure; do not synthesize again to fix a sidecar.

</Run>
