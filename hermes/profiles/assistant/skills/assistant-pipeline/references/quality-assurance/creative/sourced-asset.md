# QA contract — sourced asset

The orchestrating assistant performs a read-only inspection of the externally sourced asset package at its durable path.

## Scope
Inspect the delivered bytes and provenance package for sourced assets, including
meme templates, GIFs, and brand marks. Research evidence supplied in the flow
establishes external truth; QA checks that the candidate package represents it and
remains unchanged.

## Required inputs
The candidate package at its durable path, exact source URL/provider/identity
record, downloaded byte/format metadata, attribution and license-caveat
requirements, and the research evidence supplied in the flow for provenance and
rights claims.

## Checks
1. Inspect the actual delivered bytes; remeasure format, dimensions,
   duration/streams when applicable, and compare identity to the record.
2. Confirm source URL, provider, item ID or archive identity, attribution, and
   license caveat are present and internally consistent without web research.
3. Compare candidate bytes to the unchanged source/package anchor where supplied;
   check that any requested delivery wrapper did not alter the source asset.
4. Record package evidence and findings in the verdict/feedback.

## Not verified / never do
Missing research provenance/rights evidence, source identity, attribution or
license caveat, inaccessible bytes, or mismatch to the unchanged candidate means
NOT verified — obtain the missing input or state plainly it cannot be checked. Do
not fetch independently, alter, crop, convert, infer rights, or publish.
