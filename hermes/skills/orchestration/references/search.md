# Search approach — reference

Loaded after Step 3 picks **Approach=Search**. Dispatches retrieval work to
searcher.

## When to pick Search

- **Retrieval**: web/X search, links, latest/current info, single-source
  lookups, candidate/example enumeration, exhaustive multi-hop source hunts.
- Examples: "what's new in X 2026", "find the docs for library Y version
  Z", "collect real examples of X", "find everything about topic Y".

For analysis/synthesis/comparison, use Research instead
(`references/research.md`).

## Dispatching

Standard `<TaskSpec>` shape with:

- `assignee: searcher`
- `workspace_kind: scratch` (searcher doesn't need isolation)
- `skills: ["searcher-pipeline"]` — mandatory on every searcher card: the
  dispatcher preloads the kernel mechanically, guaranteeing mode routing and
  the link-integrity floor.
- Body: Goal / Inputs / Done criteria / Output / Constraints. Searcher
  routes itself by the deliverable — write what you want, not how:
  - a **specific answer** ("which version", "who said") → keep Done criteria
    at "answered with sources".
  - an **enumeration / survey / measurement** → give a floor count and the
    per-item fields you need ("≥15 candidates, each with pricing page URL
    and date"); searcher will attach a coverage statement.
  - an **exhaustive hunt** (obscure/contested topic, provenance, "find
    everything") → also set `goal_mode` (below).

For exhaustive hunts, add:

- `goal_mode: true` (+ `goal_max_turns`) — a judge loops the worker one
  retrieval hop per turn until coverage saturates or the budget ends. This
  is the signal that routes searcher into its multi-hop Hunt mode; no extra
  skill pin is needed (`deep-retrieval` is a deprecated stub).

## Dispatch tick reminder

Dispatch ticks run ~every 15s, so never send quick lookups (a 30-second
job) to the board — answer those Inline instead. Search is for jobs that
genuinely benefit from the searcher toolset (web/X, link harvesting,
multi-hop).

## After dispatch

Standard Step 7 mechanics. Searcher rarely blocks (only an empty/unusable
body triggers a `Q1`); on completion, summarize the findings in chat —
don't paste raw worker output.
