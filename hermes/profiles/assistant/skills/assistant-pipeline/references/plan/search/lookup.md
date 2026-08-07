# Lookup — decision surface

A specific sourced answer: a fact, a link or document, "latest on
X", who-said-what. The searcher owns query strategy and source
triage; you own what question is being answered and what counts as
answered.

Searcher unit `lookup` · QA `lookup` · units: one settled question
per unit; a batch of related questions releases as one unit with an
itemized list. Never a card — chat work or a session turn.

## Fix before release

- **The question** — one line per item; a lookup that cannot be
  stated in one line is not a lookup (route to `sweep.md` or
  `hunt.md`, or fix the question first).
- **Answered means** — the fact with a resolving source, the
  document itself, the dated statement — observable, so the turn
  can end.
- **Freshness** — "latest" needs a window; version- and
  price-shaped answers need the as-of date carried.
- **Source preference** — official/primary first by default; name
  it when only a specific source class settles the question
  (vendor docs, the paper, the author's own statement).
- **Language / region** — when it changes the result (pricing,
  availability, ja/en docs).

## Defaults

- A one-minute single fact is Chat-inline; a handful of parallel
  items for a waiting user is `delegate_task`
  (`../../chat/lookups.md`). Release a lookup unit only when the
  answers must be durable, batched, or feed a supervised session.
- Ambiguous-but-workable questions are released as-is: the searcher
  states its interpretation as the first line and proceeds —
  retrieval is cheap, a labeled assumption beats a round-trip.
- Conflicting sources come back side by side, dated — deciding
  between them is yours or the researcher's, and that is not a
  defect of the lookup.

## Red flags

- "Research X" with no question — there is nothing to answer;
  fixing the question is plan work, not the searcher's.
- The lookup actually wants a verdict, ranking, or comparison —
  that is a researcher unit, however small it looks.
- Answer-by-answer follow-ups growing hops mid-unit — a provenance
  chase is a hunt unit (granularity finding), not lookup N+1.
- A question whose answer you would not accept without analysis —
  the unit is mis-typed, not underperformed.
