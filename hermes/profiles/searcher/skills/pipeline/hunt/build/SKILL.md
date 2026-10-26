---
name: build-hunt
description: >-
  Hunt, Build stage: follow the trail hop by hop from secondary mentions to
  primary documents with a running ledger until saturation, the done criteria
  or the cap, check and hand off a source map. Requires the client's
  agreement from Plan; not long sweeps or verdicts.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
    tags: [search, hunt, build]
---

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn mode, stage or
scope change, require full-body kernel and this stage entry in current context,
not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` before any stage; its `<Build>` section
is the stage this entry specializes. Load `skill_view(name="build-hunt")`.
Retrieval on a service also requires its shared reference:
[X](../../references/platforms/x.md), [YouTube](../../references/platforms/youtube.md),
[note](../../references/platforms/note.md), [Substack](../../references/platforms/substack.md),
[EVM](../../references/platforms/evm.md), [Solana](../../references/platforms/solana.md) or
[Hyperliquid](../../references/platforms/hyperliquid.md). A technic the brief names or
[Capabilities](../../references/capabilities.md) matches is loaded too with
`skill_view(name="<technic>")`; it adds to this mode and never replaces it.
If unchanged is returned while the earlier body is unavailable, or a body is
missing, use read_file on canonical `${HERMES_SKILL_DIR}/../../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md` and
`${HERMES_SKILL_DIR}/../../references/platforms/<service>.md`. Follow
next_offset through actual truncation; stop the affected action if
unavailable. Never evade dedup with alternate paths or artificial ranges. Raw
skill_dir is this entry's directory. Loading does not restart coverage or the
frontier, reset a budget or replay work. Expansion needs the caller's release;
selection is not a new grant.

</ReadBeforeWork>

# Hunt: Build

Use for **exhaustive source hunts**: obscure topics, contested claims
needing primary sources, provenance chases — always against the agreed done
criteria and scope exclusions. Deliverable = a structured **source map**
built by following the trail from secondary mentions to primary documents.
Depth of coverage — still retrieval, not analysis or conclusions.

Dispatch shape: a hunt is one resident conversation. Keep running hops in the
turn until coverage saturates, the done criteria are met or the agreed effort
cap is spent. If the turn must end first, hand off with the ledger and the
gaps stated; the caller continues in the same conversation, and consumed
budget carries over.

## Build

### Hop loop

Each hop:

1. **Frontier** — pick the most promising open leads from the ledger (unread
   citations, named authors/orgs, referenced documents, dissenting mentions).
2. **Retrieve** — `web_search` / `x_search` / direct URL reads on those leads,
   and the service tools for a lead that lives on X, YouTube, note or
   Substack; prefer primary documents (papers, filings, specs, first-party
   posts) over coverage of them.
3. **Extract leads** — every new hit yields citations, names, and documents;
   push them onto the frontier. Note claim-level agreements/conflicts between
   sources (flag only — don't adjudicate).
4. **Ledger update** (in your running output, so it survives into the next turn):
   sources found this hop, leads opened, leads exhausted, coverage gaps.

Stop when a hop yields mostly duplicates or dead ends (saturation), the
question's sub-areas each have primary-source coverage, or the budget is
nearly spent — then write the hand-off.

### Pitfalls

- Re-searching the same phrasing each hop instead of following extracted leads.
- Stopping at secondary coverage when a primary document is one hop away.
- Losing the ledger between turns — restate it every hop.
- Sliding into synthesis or verdicts; flag conflicts and move on.
- Ignoring saturation and burning the whole budget on hop one's breadth.

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

## Verification

- Every source-map entry has a retrieved URL, source/author, date and
  primary/secondary mark; conflicts are flagged, not resolved.
- The trail shows at least one hop beyond initial search results, or explicitly
  reports why that requirement is unmet. Trail notes show who cites whom.
- Each hop retains sources found, leads opened/exhausted and coverage gaps;
  frontier is followed rather than replaying the same phrasing or losing state.
- Gaps state what was NOT found, where it might live, and what Researcher must
  verify or synthesize. Silence is not coverage.
- Done criteria, exclusions, saturation and budget match the ledger. A turn
  that ended before saturation states why, hands back the ledger and gaps, and
  stays within the agreed cap.

## Handoff

Build ends, in the same turn, with the check against this entry's
Verification, and the reply carries it; the kernel's Build section says how
the report is delivered. Expansion goes to
[plan-hunt](../plan/SKILL.md) and client agreement. Keep this mode
for the unit; another kind of retrieval is another agreed unit with its own
entries, never a silent switch.
