---
name: qa-ascii-video
description: Read-only QA inspection of an immutable ASCII video artifact.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, ascii-video, terminal, glyphs, sync]
    category: technic
---
<Scope>
Inspect sampled frames and encoded streams of the actual ASCII video. Apply
terminal and glyph rules over time; do not convert, stabilize, or re-render it.
</Scope>

<RequiredEvidence>
The immutable video and digest, terminal rows/columns, cell font/glyph policy,
ANSI/plain policy, fps/duration, audio/caption/loop requirements, and Researcher
evidence for external claims.
</RequiredEvidence>

<ChecksProcedure>
1. Reprobe duration, fps, dimensions, streams, codec/container, and size; sample
   frames at dark/light extremes, scene changes, and the loop boundary.
2. Measure terminal geometry and inspect glyph stability, alignment, coverage,
   brightness mapping, palette/ANSI or plain-text compliance, and overflow over
   time rather than trusting a still.
3. Check audio and caption timing against the sampled visual timeline and inspect
   the last-to-first transition when looping.
4. Return frame/timecode and cell-region findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Unreadable media, insufficient temporal samples, undefined terminal/ANSI policy,
or missing Researcher evidence is `can't_verify`. Do not alter glyphs, timing,
ANSI, audio, captions, re-encode, or publish.
</FailOrCantVerify>
