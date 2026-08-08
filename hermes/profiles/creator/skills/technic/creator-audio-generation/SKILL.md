---
name: creator-audio-generation
description: >-
  Creator's metered leaf technic for AudioCraft music, ambience, and sound
  effects with explicit model, hardware, provenance, and audio QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, audiocraft, musicgen, audiogen, music, sound-effects]
    category: technic
---

<Goal>
Generate an instrumental music or sound asset whose source prompt, model,
conditioning, runtime cost, and measured audio properties are reproducible.
The canonical identity is `creator-audio-generation`; the official
`audiocraft-audio-generation` skill is its implementation engine.
</Goal>

<Scope>
Use MusicGen for text-, melody-, or style-conditioned instrumental music and
AudioGen for ambience or sound effects. Full vocal songs from approved lyrics
belong to `creator-song-generation`; speech belongs to `core:tts`; analysis of
existing audio belongs to `creator-audio-visualization`.
</Scope>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
- Load `skill_view(name="audiocraft-audio-generation")`; keep the official
  engine authoritative and this canonical name stable.
- Every model invocation, including a failed run that consumed compute, counts
  as one generated-audio render. Supporting media is budgeted separately.
- Do not install packages, download model weights, change an environment, or
  accept a model/license on the user's behalf. Missing prerequisites block.
- Supplied melody/style references require recorded provenance and permission;
  never infer commercial rights from a technically successful generation.
</Contract>

<Preflight>
Check Python, PyTorch, torchaudio/transformers or AudioCraft, `ffmpeg`/`ffprobe`,
free disk space, writable cache/output paths, and the exact requested model.
Measure available CPU/GPU/RAM/VRAM against that model and duration before load.
Confirm whether model weights are already present; downloading them requires
explicit authorization. Validate reference-audio format, duration, ownership,
sample rate, channels, and the destination's loudness/codec requirements.
</Preflight>

<Procedure>
1. Record mode (`music`, `melody`, `style`, or `sound-effect`), duration, prompt,
   model/version, seed when supported, sampling parameters, count, references,
   and output contract from the released spec into a saved generation spec (open
   decisions are spec gaps).
2. Write a task-local executable script from the official engine's current API;
   do not use an inline interpreter command. Generate only within the effective
   audio-render Budget and preserve logs for failed as well as successful runs.
3. Save a lossless master before any delivery conversion. Normalize sample rate,
   channels, trim/fades, codec, and loudness only as declared by the brief; keep
   the untouched model output for diagnosis.
4. Run `ffprobe` plus loudness, peak/clipping, silence, and duration analysis.
   Render a waveform or spectrogram for structural inspection and compare any
   conditioned source without redistributing it.
5. Preserve the prompt/spec, model identity, parameters, script, logs, probe,
   QA evidence, master, and requested derivatives for pipeline handoff.
</Procedure>

<Verification>
- Prompt, model, conditioning source, attempts, outputs, and the pipeline spend
  tally reconcile exactly.
- Duration, sample rate, channel layout, codec/container, loudness, peak level,
  silence, clipping, and file size meet the brief and contain no invalid stream.
- A waveform/spectrogram can reveal truncation or structural gaps but cannot
  prove musical quality. Record a real listen-through when available; otherwise
  state the perceptual limitation instead of claiming timbre, mix, or mood passed.
- Deliver the lossless master when requested, the destination derivative, and
  reusable prompt/seed/conditioning metadata without unlicensed source media.
</Verification>
