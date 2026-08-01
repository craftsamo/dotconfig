---
name: qa-sourced-asset
description: Read-only QA inspection of an immutable externally sourced asset package.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, sourcing, provenance, attribution, license]
    category: technic
---
<Scope>
Inspect the delivered bytes and provenance package for sourced assets, including
meme templates, GIFs, and brand marks. Researcher establishes external truth;
QA checks that the candidate package represents it and remains unchanged.
</Scope>

<RequiredEvidence>
The immutable candidate and digest, exact source URL/provider/identity record,
downloaded byte/format metadata, attribution and license-caveat requirements,
and the predeclared Researcher evidence for provenance and rights claims.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and inspect the actual delivered bytes; remeasure format, dimensions,
   duration/streams when applicable, and compare identity to the record.
2. Confirm source URL, provider, item ID or archive identity, attribution, and
   license caveat are present and internally consistent without web research.
3. Compare candidate bytes to the unchanged source/package anchor where supplied;
   check that any requested delivery wrapper did not alter the source asset.
4. Return package evidence and findings to `qa-pipeline`'s verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
Missing Researcher provenance/rights evidence, source identity, attribution or
license caveat, inaccessible bytes, or mismatch to the unchanged candidate is
`can't_verify`. Do not fetch independently, alter, crop, convert, infer rights,
or publish.
</FailOrCantVerify>
