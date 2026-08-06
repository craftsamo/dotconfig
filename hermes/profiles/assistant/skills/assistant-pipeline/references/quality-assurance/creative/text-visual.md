# QA contract — text visual

The orchestrating assistant performs a read-only inspection of the exact-copy text visual at its durable path.

## Scope
Inspect the actual rendered text visual, including text cards and memes. A
sourced meme template also requires the `qa-sourced-asset` contract; this leaf
checks composition and copy, not external provenance truth.

## Required inputs
The render at its durable path, canonical copy including required whitespace and
line breaks, typography/destination/safe-area brief, and source-template handoff
when applicable. Research evidence supplied in the flow is required for external
factual claims.

## Checks
1. Inspect native and destination-size renders. Read every character,
   punctuation mark, line break, and required whitespace back against the copy.
2. Check font coverage, hierarchy, contrast, wrapping, clipping, overlap,
   accidental text, and safe-area margins at native and thumbnail sizes.
3. For a meme, verify caption-field order and composition against the supplied
   template record; defer template identity, URL, and rights to
   `qa-sourced-asset`.
4. Record location-specific evidence and findings in the verdict/feedback.

## Not verified / never do
Unreadable text, missing canonical copy/template evidence, inaccessible render,
or missing research evidence supplied in the flow for a gating fact means NOT
verified — obtain the missing input or state plainly it cannot be checked. Never
rewrite copy, retouch text, change typography, recompose, re-export, or publish.
