# QA contract — fact-check

The orchestrating assistant performs a read-only inspection of the
verdicts in the reply — and the complete ledger at its durable path
when the brief named a consumer — measured against the brief's
claims list and source requirements. Applies to session units and
`claim-verification` cards alike.

## Scope
Inspect the verdict set as findings-only verification: claim
completeness, verdict grounding, ledger integrity. Never re-verify
claims yourself or soften a verdict.

## Required inputs
The released brief or card body (fixed claims list, source
requirements, freshness, consumer, ledger filename); every verdict
with its evidence and counterevidence; the ledger file when
required.

## Checks
1. Count the claims. Every claim in the released list has a
   verdict — none silently dropped, merged, or added; compound
   splits are noted and cover the original in full.
2. Verbatim integrity: original claims preserved byte-for-byte
   (spot-check against the source text/artifact when supplied);
   the neutral restatement did not shift what was checked.
3. Verdict grounding: each verdict's strength matches its
   corroboration per the brief's source requirements — "supported"
   carries the required primary or ≥2 independent A/B sources;
   spot-check that the cited sources say what the verdict claims.
4. Counterevidence and unverifiables: counterevidence searched per
   claim (or "none found" stated); every `unverifiable` names what
   was searched and where the answer might live.
5. Ledger: when the brief named a consumer, the complete ledger
   exists at the durable path under the named filename and matches
   the reply's verdicts — a summary-only delivery is a finding.

## Not verified / never do
A claim without a verdict, a verdict without its evidence, or a
missing ledger means NOT verified — obtain the missing piece or
fail the unit plainly. Do not adjudicate artifact quality, re-run
the verification, or upgrade/downgrade verdicts yourself.
