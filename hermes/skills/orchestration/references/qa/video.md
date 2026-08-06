# QA contract — video

The orchestrating assistant performs a read-only inspection of the time-based video artifact at its durable path.

## Scope
Inspect the actual video artifact file at its durable path over time, never only
its first frame. Check the encoded file, spread frames, motion, streams, and
delivery behavior.

## Required inputs
The video artifact file at its durable path, expected duration/fps/dimensions/
container/codec/size, text/audio/loop/poster requirements, and research evidence
supplied in the flow for external factual claims or explainer content.

## Checks
1. Run a read-only ffprobe-like measurement of duration, frame rate, dimensions,
   streams, codec/container, bitrate, and byte size.
2. Inspect a spread of frames and motion across scene boundaries for artifacts,
   continuity, framing, and text over time; check captions/overlays for clipping
   and legibility rather than trusting the first frame.
3. Check audio presence, stream timing and sync, and when required compare the
   last-to-first loop seam and poster frame to the brief.
4. Record timecode/frame-specific evidence and findings in the verdict/feedback.

## Not verified / never do
Unreadable media, incomplete probe, unavailable sampled frames/audio, or missing
research evidence supplied in the flow for a gating claim means NOT verified —
obtain the missing input or state plainly it cannot be checked. Never trim, encode,
mute, caption, repair, generate, re-export, or publish.
