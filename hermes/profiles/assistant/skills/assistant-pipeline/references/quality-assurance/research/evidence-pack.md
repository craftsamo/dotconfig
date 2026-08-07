# QA contract — evidence-pack

The orchestrating assistant performs a read-only inspection of the
synthesis in the reply (and any report at its durable path),
measured against the brief's question and done criteria.

## Scope
Inspect the complete synthesis as findings-only verification:
categories, sourcing, corroboration, uncertainty. Never re-research
or rewrite the conclusion yourself.

## Required inputs
The released brief (question, decision context, done criteria,
source policy, effort bound); the full report with its categories
(Summary / Sources / Observations / Corroboration / Uncertainty /
Implications); any file at the durable path.

## Checks
1. Read the complete report. All categories present; the conclusion
   leads and every summary finding is backed further down — a
   summary claim with no observation behind it is a finding.
2. Source spot-check the load-bearing claims: URLs resolve, quotes
   match, dates/versions right, reliability/credibility scores
   present; single-source claims are marked single-source.
3. Done criteria: the brief's sub-questions are closed or their
   openness is stated in Uncertainty with what would close them;
   the source policy (freshness, reliability floor) was honored.
4. Separation: observation, corroboration, inference, and
   uncertainty are distinct — an inference upgraded to fact, or
   smoothed-over uncertainty, is a finding.
5. Boundary: implications inform the caller's decision without
   taking it over; no directives (guidance unit), no artifact, no
   ranking of options the brief never named.

## Not verified / never do
A missing category, an unopened load-bearing source, or a report
absent from its named durable path means NOT verified — obtain the
missing piece or fail the unit plainly. Do not patch the synthesis,
soften uncertainty, or answer the question yourself.
