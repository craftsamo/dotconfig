---
name: qa-text-visual
description: Read-only QA inspection of an immutable exact-copy text visual.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, typography, text-card, meme, legibility]
    category: technic
---

<Scope>
Inspect the actual rendered text visual, including text cards and memes. A
sourced meme template also requires the `qa-sourced-asset` contract; this leaf
checks composition and copy, not external provenance truth.
</Scope>

<RequiredEvidence>
The immutable render and digest, canonical copy including required whitespace and
line breaks, typography/destination/safe-area brief, and source-template handoff
when applicable. Researcher evidence is required for external factual claims.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and inspect native and destination-size renders. Read every character,
   punctuation mark, line break, and required whitespace back against the copy.
2. Check font coverage, hierarchy, contrast, wrapping, clipping, overlap,
   accidental text, and safe-area margins at native and thumbnail sizes.
3. For a meme, verify caption-field order and composition against the supplied
   template record; defer template identity, URL, and rights to `qa-sourced-asset`.
4. Return location-specific evidence and findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Unreadable text, missing canonical copy/template evidence, inaccessible render,
or missing Researcher evidence for a gating fact is `can't_verify`. Never rewrite
copy, retouch text, change typography, recompose, re-export, or publish.
</FailOrCantVerify>
