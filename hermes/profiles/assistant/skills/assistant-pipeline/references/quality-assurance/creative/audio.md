# QA contract — audio

The orchestrating assistant performs a read-only inspection of the audio artifact file at its durable path.

## Scope
Inspect the actual audio file mechanically, visually, and with a qualified
listen. This leaf does not mix, master, denoise, normalize, or claim unsupported
timbre, emotion, or musical quality certainty.

## Required inputs
The audio artifact file at its durable path, expected codec/container, duration,
sample rate, channels, loudness/peak limits, silence/truncation policy, and
available waveform/spectrogram and qualified listening path.

## Checks
1. Reprobe codec/container, duration, sample rate, channels, bitrate, and size;
   independently measure loudness, true/sample peak, clipping, silence, and
   truncation.
2. Inspect waveform and spectrogram for gaps, clipped regions, unexpected
   silence, dropouts, and frequency anomalies relative to the brief.
3. Perform a qualified listen where available and report perceptual limits
   explicitly; do not infer timbre, emotion, or artistic intent from metrics.
4. Record time-range and stream evidence in the verdict/feedback.

## Not verified / never do
Unreadable audio, incomplete probe, unavailable required visual/listening
evidence, or missing source constraints means NOT verified — obtain the missing
input or state plainly it cannot be checked. Do not repair silence, clip,
loudness, codec, waveform, or re-export.
