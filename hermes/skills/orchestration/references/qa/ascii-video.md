# QA contract — ascii video

The orchestrating assistant performs a read-only inspection of the ASCII video artifact file at its durable path.

## Scope
Inspect sampled frames and encoded streams of the actual ASCII video. Apply
terminal and glyph rules over time; do not convert, stabilize, or re-render it.

## Required inputs
The video artifact file at its durable path, terminal rows/columns, cell
font/glyph policy, ANSI/plain policy, fps/duration, audio/caption/loop
requirements, and research evidence supplied in the flow for external claims.

## Checks
1. Reprobe duration, fps, dimensions, streams, codec/container, and size; sample
   frames at dark/light extremes, scene changes, and the loop boundary.
2. Measure terminal geometry and inspect glyph stability, alignment, coverage,
   brightness mapping, palette/ANSI or plain-text compliance, and overflow over
   time rather than trusting a still.
3. Check audio and caption timing against the sampled visual timeline and inspect
   the last-to-first transition when looping.
4. Record frame/timecode and cell-region findings in the verdict/feedback.

## Not verified / never do
Unreadable media, insufficient temporal samples, undefined terminal/ANSI policy,
or missing research evidence supplied in the flow means NOT verified — obtain the
missing input or state plainly it cannot be checked. Do not alter glyphs, timing,
ANSI, audio, captions, re-encode, or publish.
