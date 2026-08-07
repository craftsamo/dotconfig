# QA contract — sweep

The orchestrating assistant performs a read-only inspection of the
enumeration at its durable path (or in the reply when small),
measured against the brief's coverage claim.

## Scope
Inspect the complete enumeration/survey as findings-only
verification: membership, fields, coverage, dedup. Never extend the
table or re-sweep yourself.

## Required inputs
The released brief (population definition, coverage claim + floor,
per-item fields, scope exclusions, freshness window); the complete
table at its durable path; the searcher's coverage statement
(matrix cells searched, floor met, saturation reached).

## Checks
1. Read the complete table. Every item carries all per-item fields,
   each with source URL and date — a fieldless or undated item is a
   finding, not a footnote.
2. Membership spot-check: sampled items actually belong to the
   defined population; excluded classes and already-known items are
   absent; no duplicate under a different canonical identity.
3. Link spot-check the load-bearing rows: URLs resolve and state
   what the fields claim; pricing/version/date fields match the
   page as of the stated date.
4. Coverage: the floor count is met and the coverage statement
   measures the CLAIM ("all providers with…" needs the matrix to
   show where it looked, not just what it found); thin cells are
   named, not smoothed over. For a `survey-enumeration` card,
   measure against the coverage claim in the card body.
5. Boundary: items are enumerated, not ranked, scored, or
   recommended; selection judgments appear only under
   `Open for researcher`.

## Not verified / never do
A missing coverage statement, an unmet floor with no named gap, or
a table absent from its durable path means NOT verified — obtain
the missing piece or fail the unit plainly. Do not add items, fix
fields, re-order by preference, or decide which items matter.
