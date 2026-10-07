# Hunt unit — multi-hop retrieval to saturation

Loaded for **exhaustive source hunts**: obscure topics, contested claims
needing primary sources, provenance chases — always against the brief's
done criteria and scope exclusions ("find everything" with neither is a
spec gap, not a hunt).
Deliverable = a structured **source map** built by following the trail from
secondary mentions to primary documents. Depth of coverage — still retrieval,
not analysis or conclusions.

Dispatch shape: a hunt is one resident conversation. Keep running hops in the
turn until coverage saturates, the done criteria are met or the agreed effort
cap is spent. If the turn must end first, hand off with the ledger and the
gaps stated; the caller continues in the same conversation, and consumed
budget carries over.

## Hop loop

Each hop:

1. **Frontier** — pick the most promising open leads from the ledger (unread
   citations, named authors/orgs, referenced documents, dissenting mentions).
2. **Retrieve** — `web_search` / `x_search` / direct URL reads on those leads;
   prefer primary documents (papers, filings, specs, first-party posts) over
   coverage of them.
3. **Extract leads** — every new hit yields citations, names, and documents;
   push them onto the frontier. Note claim-level agreements/conflicts between
   sources (flag only — don't adjudicate).
4. **Ledger update** (in your running output, so it survives into the next turn):
   sources found this hop, leads opened, leads exhausted, coverage gaps.

Stop when a hop yields mostly duplicates or dead ends (saturation), the
question's sub-areas each have primary-source coverage, or the budget is
nearly spent — then write the hand-off.

## Output template

```text
## Source map
### <sub-topic / claim>
- <title> — <URL> (<source/author>, <date>) [primary|secondary] [flag?]
…
## Trail notes
- <who cites whom / how leads connected — one line each>
## Gaps
- <what could not be found or verified, and where it might live>
Open for researcher: <what needs synthesis or adjudication>
```

Primary/secondary marked on every entry; conflicts flagged, not resolved.

## Pitfalls

- Re-searching the same phrasing each hop instead of following extracted leads.
- Stopping at secondary coverage when a primary document is one hop away.
- Losing the ledger between turns — restate it every hop.
- Sliding into synthesis or verdicts; flag conflicts and move on.
- Ignoring saturation and burning the whole budget on hop one's breadth.
