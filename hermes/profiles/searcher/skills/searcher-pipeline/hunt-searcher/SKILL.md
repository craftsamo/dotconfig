---
name: hunt-searcher
description: >-
  Hunt: follow primary-source trails; retrieval only. Use for a released
  multi-hop source or provenance hunt with done criteria and scope exclusions.
  Not a candidate sweep, truth adjudication, synthesis or production task.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: searcher-pipeline
    tags: [search, hunt]
---

<ReadBeforeWork>

Re-evaluate the entry every caller, judge, resume or completion turn and before
an action whose unit or scope changes. Reuse full-body instructions only while
present in the current context, not a past load or summary. Direct entry requires
the full kernel before searching, including its runtime and card gate:

```text
skill_view(name="searcher-pipeline")
```

If a tool returns unchanged while the earlier body is unavailable, use read_file
on `${HERMES_SKILL_DIR}/../SKILL.md` for the kernel and
`${HERMES_SKILL_DIR}/SKILL.md` for this entry. Follow next_offset until the whole
required document is available; do not invent alternate paths or artificial
ranges to evade dedup. If the body remains missing, stop the affected search and
report the missing instructions; on a card follow the kernel's blocking protocol,
never claim completion. In raw file text, HERMES_SKILL_DIR is this entry's directory.

Loading does not restart coverage or the frontier, reset a budget, or release
another unit. Preserve the initial purpose and settled constraints. A change
outside the released unit requires the caller's release, not self-decomposition.
This entry owns the unit procedure and checks below; do not also load every entry.

</ReadBeforeWork>

# Hunt unit — multi-hop retrieval to saturation

Loaded for **exhaustive source hunts**: obscure topics, contested claims
needing primary sources, provenance chases — always against the brief's
done criteria and scope exclusions ("find everything" with neither is a
spec gap, not a hunt).
Deliverable = a structured **source map** built by following the trail from
secondary mentions to primary documents. Depth of coverage — still retrieval,
not analysis or conclusions.

Dispatch shape: hunts are normally dispatched with `goal_mode: true` — treat
**each turn as one hop**; the judge continues you until coverage saturates or
the budget ends. Without `goal_mode` (single-shot card), run 2-3 hops inline
in one turn, then hand off with the gaps stated.

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
4. **Ledger update** (in your running output, so it survives judge turns):
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

## Handoff

Verify every source URL and its primary/secondary mark, then deliver the
findings — sources, hop coverage, gaps — in the final reply/message.

## Pitfalls

- Re-searching the same phrasing each hop instead of following extracted leads.
- Stopping at secondary coverage when a primary document is one hop away.
- Losing the ledger between turns — restate it every hop.
- Sliding into synthesis or verdicts; flag conflicts and move on.
- Ignoring saturation and burning the whole budget on hop one's breadth.

## Verification

- Every entry has URL, source, and a primary/secondary mark.
- The trail shows at least one hop past the initial search results.
- Gaps section states what was NOT found — silence is not coverage.
- Hand-off names what researcher must verify or synthesize.
