---
name: qa-video
description: Read-only QA inspection of an immutable time-based video artifact.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, video, temporal, ffprobe, synchronization]
    category: technic
---

<Scope>
Inspect the actual video attachment over time, never only its first frame. Check
the encoded file, spread frames, motion, streams, and delivery behavior.
</Scope>

<RequiredEvidence>
The immutable video and digest, expected duration/fps/dimensions/container/codec/
size, text/audio/loop/poster requirements, and any Researcher evidence for
external factual claims or explainer content.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and run a read-only ffprobe-like measurement of duration, frame rate,
   dimensions, streams, codec/container, bitrate, and byte size.
2. Inspect a spread of frames and motion across scene boundaries for artifacts,
   continuity, framing, and text over time; check captions/overlays for clipping
   and legibility rather than trusting the first frame.
3. Check audio presence, stream timing and sync, and when required compare the
   last-to-first loop seam and poster frame to the brief.
4. Return timecode/frame-specific evidence and findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Unreadable media, incomplete probe, unavailable sampled frames/audio, or missing
Researcher evidence for a gating claim is `can't_verify`. Never trim, encode,
mute, caption, repair, generate, re-export, or publish.
</FailOrCantVerify>
