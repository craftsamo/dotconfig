---
name: creator-audio-visualization
description: >-
  Creator's deterministic leaf technic for songsee audio visualizations with
  locked analysis inputs, reproducible commands, and visual QA.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, audio, visualization, songsee, spectrogram]
    category: technic
---

<Goal>
Produce a readable, reproducible visualization of an existing audio source.
The canonical dispatch identity is `creator-audio-visualization`; analysis is
not audio generation and has zero generation cost.
</Goal>

<Scope>
Load the official `songsee` engine with `skill_view(name="songsee")`. Supported
visualizations are spectrogram, mel, chroma, hpss, selfsim, loudness, tempogram,
mfcc, and flux, in single or multi-panel layouts. Audio generation is out of
scope. Route generated supporting media through its canonical leaf.
</Scope>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
- Do not create a second intake, budget, review, or clarification protocol.
- Do not install `songsee`, `ffmpeg`, or any other dependency. Missing required
  capability is a production block, even when the skill itself is valid.
- If source audio came from `core:tts`, record its backend and use a separate
  Budget and handshake. Do not synthesize audio in this technic.
</Contract>

<Preflight>
`songsee` is mandatory. Check that the input path is readable and that the
source is WAV or MP3; for other formats, require `ffmpeg` for a declared
conversion and block if it is absent. Use `ffprobe` to record duration, stream,
sample rate, channels, and codec. Check the requested time slice is within the
source and reject an empty or unreadable range.
</Preflight>

<Procedure>
1. Load the official engine and lock input path, duration or time slice, viz
   list, style, width, height, format, and output path from the brief.
2. Save the exact `songsee` command and flags, any conversion command, source
   probe, and parameters in the task workspace before rendering.
3. Render one representative output first. Use a saved project or official
   script; do not use an inline interpreter that violates the worker guard.
4. Check output dimensions and format, labels and axes, time coverage, panel
   correspondence, blank regions, clipping, and readable contrast with vision.
5. Render the final only after the locked preview passes. Keep source, probe,
   commands, logs, preview, final output, and QA notes together.
</Procedure>

<Verification>
Use `magick identify`, `sips`, or `file` to measure the result. Confirm the
declared viz panels match their labels and source time slice, dimensions and
format are exact, and no panel is blank or clipped. Deliver evidence through
the pipeline's Review, V1-V6, and delivery stages; the leaf does not own them.
</Verification>
