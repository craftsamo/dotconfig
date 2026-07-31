---
name: creator-song-generation
description: >-
  Creator's metered leaf technic for HeartMuLa vocal-song generation from
  approved lyrics and tags with hardware, structure, rights, and audio QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, heartmula, song-generation, vocals, lyrics, music]
    category: technic
---

<Goal>
Generate a full vocal song from approved lyrics and musical tags while keeping
the text, structure, model/runtime choice, and generation spend auditable. The
canonical identity is `creator-song-generation`; the official `heartmula`
skill is its implementation engine.
</Goal>

<Scope>
Use for HeartMuLa songs conditioned on lyrics plus tags. Instrumental beds,
ambience, and sound effects belong to `creator-audio-generation`. Writing or
rewriting lyrics belongs to the writer profile; Creator requires supplied or
explicitly approved lyrics before generation.
</Scope>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
- Load `skill_view(name="heartmula")`; follow its current compatibility and
  invocation guidance without copying version-sensitive patches into this leaf.
- Each model invocation that consumes compute counts as one song render,
  including failed or rejected attempts. A long/full song without a locked
  direction enters the pipeline's plan/anchor gate before full rendering.
- Never clone, patch, install, download multi-GB checkpoints, or accept a model
  license without explicit authorization. Never silently switch to a hosted
  service or another song model.
- Record lyric/reference ownership and intended usage. Technical output does not
  establish copyright, voice likeness permission, or commercial clearance.
</Contract>

<Preflight>
Check the official skill, exact heartlib/model versions, required Python,
checkpoint completeness, `ffmpeg`/`ffprobe`, free disk/RAM, and writable output.
Measure GPU/VRAM availability and estimate runtime before spend. Block when the
estimate exceeds the pipeline's effective `Runtime:` ceiling; a CPU-only path
also requires `CPU fallback: allowed` in `Budget:` or `AUTHORITY+:`. Confirm
lyrics encoding and language, structural tags, style tags, target duration,
vocal constraints, prohibited likenesses, and destination audio specification.
</Preflight>

<Procedure>
1. Save the approved lyrics byte-for-byte, structural tags, musical tags,
   language, model/version, duration, seed/sampling parameters, and output spec.
2. For a high-cost full song, produce only the pipeline-approved short anchor or
   planning evidence first. Do not launch the final render before sign-off.
3. Invoke a saved task-local script or the official example within the effective
   song-render Budget. Preserve stdout/stderr, elapsed time, model identity, and
   every generated file, including failed attempts needed for diagnosis.
4. Keep the native output, then make declared delivery derivatives without
   overwriting it. Measure streams, loudness, peaks, clipping, silence, and
   duration; create waveform/spectrogram evidence and a transcript when useful.
5. Compare section order and any transcript evidence with the approved lyrics.
   Mark unintelligible, omitted, repeated, or altered lines as review risks; do
   not present imperfect transcription as proof of exact sung words.
6. Hand the approved lyrics/tags, generation spec, logs, probes, QA evidence,
   master, and requested derivative to pipeline V1-V6 and Review.
</Procedure>

<Verification>
- Lyrics/tags, model parameters, render attempts, output files, and spend tally
  reconcile; the final was not rendered before a required anchor sign-off.
- Duration, format, sample rate, channels, bitrate, loudness, peak/clipping,
  silence, and section order meet the brief.
- Automated transcription is supporting evidence only. Exact lyric fidelity,
  vocal quality, arrangement, and emotional fit require a real listen-through;
  report that limitation honestly when no qualified review occurred.
- No unapproved living-artist imitation, voice likeness, or uncleared reference
  is claimed as safe. Attach only approved outputs and reusable non-infringing
  generation metadata.
</Verification>
