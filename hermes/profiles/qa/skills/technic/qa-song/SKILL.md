---
name: qa-song
description: Read-only QA inspection of an immutable vocal song and lyric delivery.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, song, lyrics, vocals, transcription]
    category: technic
---
<Scope>
Apply `qa-audio` checks to the actual song, then inspect approved lyric fidelity,
section structure, and vocal boundaries. Do not rewrite lyrics or audio.
</Scope>

<RequiredEvidence>
The immutable audio and digest, approved lyrics byte-for-byte with section order,
target duration and delivery limits, transcription/listening evidence, and
Researcher evidence for factual or externally sourced lyric claims.
</RequiredEvidence>

<ChecksProcedure>
1. Reprobe and measure all `qa-audio` fields, including loudness, peaks, silence,
   clipping, waveform, and spectrogram.
2. Use transcription as supporting evidence and a qualified listen when needed
   to read vocals against approved lyrics verbatim; identify omitted, repeated,
   altered, or unintelligible lines.
3. Check section order/completeness and vocal entry/end truncation against the
   approved structure; cite time ranges and lines.
4. Return evidence and findings to `qa-pipeline`; Researcher establishes facts,
   not QA.
</ChecksProcedure>

<FailOrCantVerify>
Missing approved lyrics/structure, unreadable audio, insufficient transcription
or qualified listening for exactness, or missing Researcher evidence is
`can't_verify`. Never rewrite lyrics, edit vocals, retrim, remix, or re-export.
</FailOrCantVerify>
