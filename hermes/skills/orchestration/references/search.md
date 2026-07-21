# Search approach — reference

Loaded after Step 3 picks **Approach=Search**. Dispatches retrieval work to
searcher.

## When to pick Search

- **Retrieval**: web/X search, links, latest/current info, single-source
  lookups, shallow multi-hop.
- Examples: "what's new in X 2026", "find the docs for library Y version
  Z", "who said X about topic Y".

For **exhaustive** multi-hop source hunts (research-grade), use the
`deep-retrieval` skill + `goal_mode` (below). For analysis/synthesis/
comparison, use Research instead (`references/research.md`).

## Dispatching

Standard `<TaskSpec>` shape with:

- `assignee: searcher`
- `workspace_kind: scratch` (searcher doesn't need isolation)
- Body: Goal / Inputs / Done criteria (e.g. "N authoritative sources, each
  with publication date and a one-line relevance summary") / Output /
  Constraints.

For exhaustive hunts, add:

- `skills: ["deep-retrieval"]` — force-loads searcher's specialist skill
  for multi-hop query expansion + source-class routing.
- `goal_mode: true` (+ `goal_max_turns`) — a judge loops the worker until
  done or budget exhausted. Pair with deep-retrieval for source hunts that
  rarely finish in one shot.

## Dispatch tick reminder

Dispatch ticks run ~every 15s, so never send quick lookups (a 30-second
job) to the board — answer those Inline instead. Search is for jobs that
genuinely benefit from the searcher toolset (web/X, link harvesting,
multi-hop).

## After dispatch

Standard Step 7 mechanics. Searcher rarely blocks; on completion, summarize
the findings in chat — don't paste raw worker output.
