# QA contract — ascii art

The orchestrating assistant performs a read-only inspection of the ASCII-art artifact file at its durable path.

## Scope
Inspect the actual plain-text ASCII master and required preview/source record.
This leaf does not convert, normalize whitespace, add ANSI, or publish artwork.

## Required inputs
The UTF-8/plain master, terminal width/height, monospace font, glyph set,
whitespace and ANSI policy, and preview/source attribution when the work uses an
image or remote source. Research evidence supplied in the flow settles external
source claims.

## Checks
1. Decode the master as UTF-8; record line count, display width per line,
   trailing whitespace, control/ANSI escapes, and terminal bounds.
2. Check monospace alignment, glyph coverage, blank/overflow lines, requested
   whitespace policy, and legibility in the declared terminal geometry.
3. Compare the preview with the plain source and inspect source URL/signature or
   attribution where applicable; do not infer provenance independently.
4. Record exact line/column evidence and findings in the verdict/feedback.

## Not verified / never do
Decode failure, missing geometry/policy, unavailable required preview, or missing
source attribution/evidence means NOT verified — obtain the missing input or state
plainly it cannot be checked. Do not strip escapes, reflow lines, substitute
glyphs, rewrite, or publish.
