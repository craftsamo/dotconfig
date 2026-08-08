# QA contract — lookup

The orchestrating assistant performs a read-only inspection of the
lookup findings in the searcher's reply (or the file a batch names).

## Scope
Inspect the answer(s) to the released question(s) as findings-only
verification. One check per question in a batch. Never re-run the
search yourself beyond opening what was cited.

## Required inputs
The released question list with its answered-means criteria,
freshness window, and source preference; the searcher's reply with
per-answer sources and dates, and its interpretation line when the
brief was assumed-on.

## Checks
1. Every released question has an answer or a named miss — none
   silently dropped; a batch reports item by item.
2. Open each answer's source: the URL resolves and the page
   actually states the claim — quotes verbatim, numbers and
   versions matching, the statement attributed to who said it.
3. Dates: time-sensitive answers carry the source's date and fall
   inside the freshness window; "latest" answers name their as-of
   moment; stale hits are flagged, not mixed in.
4. Source preference honored: official/primary where the brief
   demanded it; conflicting sources presented side by side and
   dated, not adjudicated.
5. Boundary: the answer is retrieval — any verdict, ranking, or
   recommendation is a finding, as is an unlabeled interpretation
   of an ambiguous question.

## Not verified / never do
An answer whose source does not resolve, an unstated date on a
time-sensitive claim, or a missing interpretation line on an
assumed brief means NOT verified — return the item, not the unit's
polish. Do not answer the question yourself, extend the search, or
decide between conflicting sources.
