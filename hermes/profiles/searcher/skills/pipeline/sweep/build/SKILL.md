---
name: build-sweep
description: >-
  Sweep, Build stage: enumerate the agreed population cell by cell from a
  coverage matrix, capture per-item fields, dedupe by identity, write the
  coverage statement, check and hand off. Requires the client's agreement from
  Plan; not specific answers, source trails or rankings.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
    tags: [search, sweep, build]
---

<ReadBeforeWork>

On every caller, resume or completion turn and before a midturn mode, stage or
scope change, require full-body kernel and this stage entry in current context,
not a past load or summary. Direct entry requires
`skill_view(name="searcher-pipeline")` before any stage; its `<Build>` section
is the stage this entry specializes. Load `skill_view(name="build-sweep")`.
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

# Sweep: Build

Use when the unit wants **"collect / enumerate / survey as many
as possible"**: candidates, examples, instances — or a measured observation
of public web state. Deliverable = a deduped list **plus an explicit coverage
statement** (what was searched, what was not). The brief's floor count is a
floor, not a target to stop at exactly.

## Build

### Steps

1. **Build a coverage matrix first.** Derive the axes from the brief (e.g.
   platform × category × time window; or the candidate space's own
   dimensions). Write the query families per cell BEFORE searching — this is
   what makes the coverage claim honest later.
2. **Enumerate cell by cell.** Official / primary sources first, then general
   `web_search`, `x_search` for current/community signal, forums for lived
   experience. A cell on a service (YouTube, note, Substack, X) is read
   through that service's tool and reference, not only through web snippets.
   Rotate phrasings inside a cell before declaring it thin.
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

### Measurement variant

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

### Pitfalls

- Stopping at page one of one engine and calling it a sweep.
- Deep-reading individual items — per-item capture stays shallow; depth is
  hunt's or researcher's job.
- Presenting an observed count as the true total.
- Sliding into ranking, scoring, or recommending — that is synthesis.
- A list without a coverage statement is not a sweep result.

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

## Verification

- Every item has a retrieved URL, source, required date and agreed per-item fields;
  dedup uses canonical identity, not merely URL.
- Coverage names searched AND unsearched cells/query families and thin/empty
  cells with their attempted queries. A page-one list alone is not a sweep.
- The Done-criteria floor is met with saturation, or shortfall and budget stop
  are explained with queries that failed to fill it. No padding to hit a number.
- Measurement records engine, exact queries, date/time, page depth and observed
  counts with truncation/personalization/estimation and engine-specific caveats.
  Observed counts are not true totals. No rankings or risk verdicts.

## Handoff

Build ends, in the same turn, with the check against this entry's
Verification, and the reply carries it; the kernel's Build section says how
the report is delivered. Expansion goes to
[plan-sweep](../plan/SKILL.md) and client agreement. Keep this mode
for the unit; another kind of retrieval is another agreed unit with its own
entries, never a silent switch.
