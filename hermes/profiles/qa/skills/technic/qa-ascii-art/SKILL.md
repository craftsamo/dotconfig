---
name: qa-ascii-art
description: Read-only QA inspection of an immutable ASCII-art text master.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, ascii, terminal, utf8, monospace]
    category: technic
---

<Scope>
Inspect the actual plain-text ASCII master and required preview/source record.
This leaf does not convert, normalize whitespace, add ANSI, or publish artwork.
</Scope>

<RequiredEvidence>
The immutable UTF-8/plain master and digest, terminal width/height, monospace
font, glyph set, whitespace and ANSI policy, and preview/source attribution when
the work uses an image or remote source. Researcher evidence settles external
source claims.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and decode the master as UTF-8; record line count, display width per
   line, trailing whitespace, control/ANSI escapes, and terminal bounds.
2. Check monospace alignment, glyph coverage, blank/overflow lines, requested
   whitespace policy, and legibility in the declared terminal geometry.
3. Compare the preview with the plain source and inspect source URL/signature or
   attribution where applicable; do not infer provenance independently.
4. Return exact line/column evidence and findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Decode failure, missing geometry/policy, unavailable required preview, or
missing source attribution/evidence is `can't_verify`. Do not strip escapes,
reflow lines, substitute glyphs, rewrite, or publish.
</FailOrCantVerify>
