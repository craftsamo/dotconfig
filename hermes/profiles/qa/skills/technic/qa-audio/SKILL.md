---
name: qa-audio
description: Read-only QA inspection of an immutable audio artifact.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, audio, loudness, waveform, spectrogram]
    category: technic
---
<Scope>
Inspect the actual audio file mechanically, visually, and with a qualified
listen. This leaf does not mix, master, denoise, normalize, or claim unsupported
timbre, emotion, or musical quality certainty.
</Scope>

<RequiredEvidence>
The immutable audio and digest, expected codec/container, duration, sample rate,
channels, loudness/peak limits, silence/truncation policy, and available
waveform/spectrogram and qualified listening path.
</RequiredEvidence>

<ChecksProcedure>
1. Reprobe codec/container, duration, sample rate, channels, bitrate, and size;
   independently measure loudness, true/sample peak, clipping, silence, and
   truncation.
2. Inspect waveform and spectrogram for gaps, clipped regions, unexpected
   silence, dropouts, and frequency anomalies relative to the brief.
3. Perform a qualified listen where available and report perceptual limits
   explicitly; do not infer timbre, emotion, or artistic intent from metrics.
4. Return time-range and stream evidence to `qa-pipeline` for verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
Unreadable audio, incomplete probe, unavailable required visual/listening
evidence, or missing source constraints is `can't_verify`. Do not repair silence,
clip, loudness, codec, waveform, or re-export.
</FailOrCantVerify>
