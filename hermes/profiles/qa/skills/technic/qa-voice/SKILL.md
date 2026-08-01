---
name: qa-voice
description: Read-only QA inspection of an immutable text-to-speech voice artifact.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, voice, tts, transcription, speech]
    category: technic
---
<Scope>
Inspect the actual TTS audio against its approved script and delivery contract.
Pronunciation is judged only where a reference is supplied; QA does not edit or
rewrite speech.
</Scope>

<RequiredEvidence>
The immutable audio and digest, approved script with exact text/order, optional
pronunciation reference, expected duration/format/rate/channels, and audio
probe/waveform evidence.
</RequiredEvidence>

<ChecksProcedure>
1. Reprobe codec/container, duration, sample rate, channels, loudness, peaks,
   clipping, silence, truncation, and file size.
2. Back-transcribe the actual speech and compare word-by-word for missing,
   wrong, reordered, or extra words; cite time ranges and script locations.
3. Check supplied pronunciation references only for named terms, then inspect
   pauses, speech entry/end, clipping, and intelligibility with a qualified
   listen where available.
4. Return evidence and bounded findings to `qa-pipeline`'s rollup.
</ChecksProcedure>

<FailOrCantVerify>
Missing script, inaccessible audio, inadequate transcription/listening, or a
pronunciation claim without a reference is `can't_verify`. Do not change words,
pronunciation, pauses, gain, codec, or re-export.
</FailOrCantVerify>
