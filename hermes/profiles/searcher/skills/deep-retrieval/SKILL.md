---
name: deep-retrieval
description: Searcher's deep multi-hop retrieval for exhaustive source hunts — iterative query refinement across hops (follow citations, authors, and primary documents), per-hop coverage ledger, saturation-based stopping, and a source-map hand-off. Dispatched explicitly via skills:["deep-retrieval"], normally with goal_mode:true so the judge loops hops until coverage saturates. Still retrieval, not synthesis — breadth-retrieval covers the default fast/wide case.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [search, retrieval, deep-dive, multi-hop, web, x_search, goal-mode]
    category: research
    related_skills: [breadth-retrieval]
---

<Goal>

Hunt a topic to saturation across multiple hops: follow the trail from
secondary mentions to primary sources, map who-cites-whom, and hand off a
structured source map. Depth of coverage — still not analysis or conclusions.

</Goal>

<Scope>
<UseWhen>

- The task explicitly loads this skill (`skills: ["deep-retrieval"]`) for an
  exhaustive hunt: obscure topics, contested claims needing primary sources,
  "find everything about X", provenance chases.
- Usually paired with `goal_mode: true` — treat each turn as one hop; the
  judge continues you until coverage saturates or the budget ends.

</UseWhen>

<DoNotUseWhen>

- Default retrieval tasks — `breadth-retrieval` (fast, wide, one pass).
- Synthesis, evaluation, or verdicts — researcher's job.

</DoNotUseWhen>
</Scope>

<HopLoop>

Each hop:

1. **Frontier** — pick the most promising open leads from the ledger (unread
   citations, named authors/orgs, referenced documents, dissenting mentions).
2. **Retrieve** — `web_search` / `x_search` / direct URL reads on those leads;
   prefer primary documents (papers, filings, specs, first-party posts) over
   coverage of them.
3. **Extract leads** — every new hit yields citations, names, and documents;
   push them onto the frontier. Note claim-level agreements/conflicts between
   sources (flag only — don't adjudicate).
4. **Ledger update** (in your running output, so it survives judge turns):
   sources found this hop, leads opened, leads exhausted, coverage gaps.

Stop when a hop yields mostly duplicates or dead ends (saturation), the
question's sub-areas each have primary-source coverage, or the budget is
nearly spent — then write the hand-off.

</HopLoop>

<OutputTemplate>

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

</OutputTemplate>

<Pitfalls>

- Re-searching the same phrasing each hop instead of following extracted leads.
- Stopping at secondary coverage when a primary document is one hop away.
- Losing the ledger between turns — restate it every hop.
- Sliding into synthesis or verdicts; flag conflicts and move on.
- Ignoring saturation and burning the whole budget on hop one's breadth.
- No write-actions on social platforms.

</Pitfalls>

<Verification>

- Every entry has URL, source, and a primary/secondary mark.
- The trail shows at least one hop past the initial search results.
- Gaps section states what was NOT found — silence is not coverage.
- Hand-off names what researcher must verify or synthesize.

</Verification>
