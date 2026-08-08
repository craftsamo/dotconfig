# QA contract — tradeoff-matrix

The orchestrating assistant performs a read-only inspection of the
matrix in the reply (or at its durable path), measured against the
brief's decision, option set, and criteria.

## Scope
Inspect the complete matrix as findings-only verification: cell
coverage, evidence per cell, recommendation. Never re-score cells
or make the domain decision inside QA.

## Required inputs
The released brief (decision, closed option set, criteria with
weights, evidence floor per cell, done criteria); the complete
matrix with sources; the recommendation with confidence.

## Checks
1. Read the complete matrix. Every released option appears; every
   criterion from the brief appears; added axes are labeled as the
   researcher's additions, not smuggled in as the caller's.
2. Cell coverage: every option × criterion cell is scored with a
   source reference or explicitly `Unknown` with what would resolve
   it — a plausible-sounding filled cell with no source is a
   finding.
3. Source spot-check the decision-driving cells and every named
   deal-breaker: URLs resolve, the page states what the cell
   claims, dates/versions right, the brief's evidence floor met.
4. Recommendation: present, singular (or explicitly conditional),
   with confidence and reasoning that traces to the matrix — a
   recommendation contradicting its own cells is a finding.
5. Boundary: options judged on the same axes; no option enumerated
   beyond the released set (an open set went unreported as a
   granularity finding); the decision itself is left to the caller.

## Not verified / never do
A missing option, an unlabeled axis, or a recommendation without
confidence means NOT verified — obtain the missing piece or fail
the unit plainly. Do not fill `Unknown` cells, reweigh criteria, or
substitute your own recommendation.
