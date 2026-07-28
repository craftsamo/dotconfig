# Gather engine — retrieval strategy and fan-out

Load when gathering goes beyond a few direct lookups: choosing between your
own tools, searcher delegation, and technic playbooks — or when part of the
task belongs on the board. The kernel's <SourceEvaluation> and
<CitationRules> govern everything gathered here.

## Search route

Breadth, in order; trace every claim to its original context:

1. Primary / official (docs, specs, papers, filings, source code) — reliability A
2. Reputable secondary (established docs/news, recognized experts) — B
3. General web — C/D; investigate the source (lateral read) before trusting
4. X / social — real-time / primary-witness value, but C–F; corroborate, never sole support
5. Reddit / forums / blogs — lived experience; D by default

Virality != truth. A high search rank is not reliability.

## Who gathers what

- **Your own web/vision/video/file tools** — depth reads, source
  inspection, media inspection: anything where your scoring judgment must
  apply at read time. Extract directly, never from memory of a snippet.
- **`delegate_task`** — quick parallel lookups you can wait out inside one
  run (a handful of URL fetches, a definition check).
- **Searcher child cards** — breadth hunts and link harvesting that would
  eat your runtime. Always pin `skills: ["searcher-pipeline"]`; for
  exhaustive multi-hop hunts add `goal_mode: true`. Searcher hands back
  links + snippets; the trust scoring stays yours.
- **Technic playbooks on this profile** — `web-source-vetting` (retrieval
  fallbacks, source independence, vendor-metric discipline) and
  `media-artifact-verification` (verified media numbers — metadata for
  figures, vision for content). The dispatcher may pin them onto the card;
  when the task turns out to need one that isn't pinned, `skill_view` it
  yourself.

## Fan-out — decompose on the board, never wait in-process

When part of the task belongs to another worker (parallel lookups, an
asset, prose, analysis) or exceeds your tools:

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread;
   e.g. parallel searcher hunts feeding one synthesis).
2. `kanban_create` a **continuation card assigned to your own profile**
   with `parents=[the child ids]`: its body says what to do with their
   results (their completion summaries/metadata arrive in the injected
   context; `kanban_show` a parent id for detail). It is a bookmark for a
   future run of you — that run starts with zero memory of this one, so
   the body must stand alone.
3. `kanban_complete` the current card ("decomposed into <ids>") and stop —
   never wait for children. The dispatcher wakes the continuation card
   when they all finish (fan-in).

Rules:

- **Grants never propagate.** Write into a child at most your own
  effective grant (advisory tasks stay read-only) — never more. A child
  that would need a wider grant is a question for the orchestrator: block
  on YOUR card, don't mint.
- Children you create notify nobody (no chat subscription); the
  orphan-watchdog cron is the safety net, not a license. Decisions that
  need the user go through your own card's block round-trip, never a
  child's.
- `delegate_task` stays right for quick in-turn parallel lookups; the
  board is for heavier or durable stages.
