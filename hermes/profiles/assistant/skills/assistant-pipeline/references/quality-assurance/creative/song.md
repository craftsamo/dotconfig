# QA contract — song

The orchestrating assistant performs a read-only inspection of the vocal song and lyric delivery at its durable path.

## Scope
Apply `qa-audio` checks to the actual song, then inspect approved lyric fidelity,
section structure, and vocal boundaries. Do not rewrite lyrics or audio.

## Required inputs
The audio artifact file at its durable path, approved lyrics byte-for-byte with
section order, target duration and delivery limits, transcription/listening
evidence, and research evidence supplied in the flow for factual or externally
sourced lyric claims.

## Checks
1. Reprobe and measure all `qa-audio` fields, including loudness, peaks, silence,
   clipping, waveform, and spectrogram.
2. Use transcription as supporting evidence and a qualified listen when needed
   to read vocals against approved lyrics verbatim; identify omitted, repeated,
   altered, or unintelligible lines.
3. Check section order/completeness and vocal entry/end truncation against the
   approved structure; cite time ranges and lines.
4. Record evidence and findings in the verdict/feedback; research evidence
   supplied in the flow establishes facts, not the verifier.

## Not verified / never do
Missing approved lyrics/structure, unreadable audio, insufficient transcription
or qualified listening for exactness, or missing research evidence supplied in the
flow means NOT verified — obtain the missing input or state plainly it cannot be
checked. Never rewrite lyrics, edit vocals, retrim, remix, or re-export.
