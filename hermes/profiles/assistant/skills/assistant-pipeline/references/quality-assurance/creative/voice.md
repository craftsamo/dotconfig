# QA contract — voice

The orchestrating assistant performs a read-only inspection of the text-to-speech voice artifact at its durable path.

## Scope
Inspect the actual TTS audio against its approved script and delivery contract.
Pronunciation is judged only where a reference is supplied; QA does not edit or
rewrite speech.

## Required inputs
The audio artifact file at its durable path, approved script with exact text/order,
optional pronunciation reference, expected duration/format/rate/channels, and
audio probe/waveform evidence.

## Checks
1. Reprobe codec/container, duration, sample rate, channels, loudness, peaks,
   clipping, silence, truncation, and file size.
2. Back-transcribe the actual speech and compare word-by-word for missing, wrong,
   reordered, or extra words; cite time ranges and script locations.
3. Check supplied pronunciation references only for named terms, then inspect
   pauses, speech entry/end, clipping, and intelligibility with a qualified listen
   where available.
4. Record evidence and bounded findings in the verdict/feedback.

## Not verified / never do
Missing script, inaccessible audio, inadequate transcription/listening, or a
pronunciation claim without a reference means NOT verified — obtain the missing
input or state plainly it cannot be checked. Do not change words, pronunciation,
pauses, gain, codec, or re-export.
