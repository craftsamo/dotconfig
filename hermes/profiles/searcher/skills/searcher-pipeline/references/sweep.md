# Sweep unit — enumeration with a coverage claim

Loaded when the released unit wants **"collect / enumerate / survey as many
as possible"**: candidates, examples, instances — or a measured observation
of public web state ("how exposed is X", "how many results for Y").
Deliverable = a deduped list **plus an explicit coverage statement** (what
was searched, what was not). The brief's coverage claim carries a floor
count — treat it as a floor, not a target to stop at exactly.

## Steps

1. **Build a coverage matrix first.** Derive the axes from the brief (e.g.
   platform × category × time window; or the candidate space's own
   dimensions). Write the query families per cell BEFORE searching — this is
   what makes the coverage claim honest later.
2. **Enumerate cell by cell.** Official / primary sources first, then general
   `web_search`, `x_search` for current/community signal, forums for lived
   experience. Rotate phrasings inside a cell before declaring it thin.
3. **Capture per item** — name/title, URL, source, date, one-line gist, plus
   whatever per-item fields the brief requires (the evidence a
   downstream researcher needs to judge each candidate).
4. **Deduplicate by canonical identity** (the product / event / account /
   document itself), not just by URL — the same candidate reached via two
   articles is one item with two sources.
5. **Keep a coverage ledger-lite in your running output**: cells covered,
   query families used, cells that came back thin or empty. It survives long
   runs and becomes the coverage statement.
6. **Stop at the floor + saturation**: the Done-criteria floor is met AND
   marginal queries return mostly duplicates — or the budget is nearly spent
   (then say which cells are uncovered).

## Measurement variant

When the brief asks for a quantified observation (counts, exposure, share of
results):

- Record the **method** inline: engine, exact queries, date/time, page depth
  observed.
- Report **observed counts as observations**, never as true totals — search
  engines truncate, personalize, and estimate; say so.
- Note engine-specific caveats (result-count display, dedup behavior) next to
  the numbers they affect.
- Still retrieval: report what was measured and how. Judgment calls,
  recommendations, and risk verdicts are researcher material — flag them
  under "Open for researcher", don't write them.

## Output template

```text
## Findings (<n> items, deduped)
- <name / title> — <URL> (<source>, <date?>) <per-item fields the brief asked for> [flag?]
…
## Coverage
- Searched: <cells / query families actually run>
- Thin or empty: <cells with little or nothing — and the queries that proved it>
- Not searched: <cells skipped and why (budget / out of scope)>
Open for researcher: <what needs verification, comparison, or a verdict>
```

## Handoff

Verify the enumerated URLs and the coverage statement, then deliver the
findings — items, searched/unsearched coverage, open gaps — in the final
reply/message.

## Pitfalls

- Stopping at page one of one engine and calling it a sweep.
- Deep-reading individual items — per-item capture stays shallow; depth is
  hunt's or researcher's job.
- Presenting an observed count as the true total.
- Sliding into ranking, scoring, or recommending — that is synthesis.
- A list without a coverage statement is not a sweep result.

## Verification

- Every item has a URL and an identified source; dedup is by canonical
  identity.
- The coverage statement names what was searched AND what was not.
- The Done-criteria floor is met, or the shortfall is explained with the
  queries that failed to fill it.
