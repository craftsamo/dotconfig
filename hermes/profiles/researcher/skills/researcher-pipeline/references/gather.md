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

- **Your own web/vision/video/file tools** — depth reads and source
  inspection. Media tools may extract a final artifact's exact factual claim
  and context; artifact-quality inspection belongs to QA. Extract directly,
  never from memory of a snippet.
- **`delegate_task`** — quick parallel lookups you can wait out inside one
  run (a handful of URL fetches, a definition check).
- **Searcher child cards** — breadth hunts and link harvesting that would
  eat your runtime. Always pin `skills: ["searcher-pipeline"]`; for
  exhaustive multi-hop hunts add `goal_mode: true`. Searcher hands back
  links + snippets; the trust scoring stays yours.
- **Learned playbooks on this profile** may inform retrieval when available,
  but are not stable dispatch identities and are never pinned by the
  orchestrator. Load one internally only when its retrieval method fits.

## Fan-out — decompose on the board, never wait in-process

When part of the task belongs to another worker (parallel lookups, an
asset, prose, analysis) or exceeds your tools:

**QA-evidence exception:** when the body names QA as the consumer or requires
an attached `claim-ledger.md`, a downstream QA card is already parented to this
Researcher task. Never complete this card into a worker-created continuation;
that would wake QA before the final ledger exists. Post a self-contained
`STATE: QA_DAG_CHANGE` comment with the Searcher child briefs, Researcher
continuation brief, exact claims, and ledger filename; then block with reason
`QA_DAG_CHANGE: protected Researcher fan-out required`. The Assistant archives
the stale QA card and registers Searcher children, the final Researcher
continuation, and replacement QA. On `DECISION(QA_DAG_CHANGE)`, complete this
checkpoint without creating duplicate cards. The normal pattern below applies
only when no QA card consumes this result.

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread;
   e.g. parallel searcher hunts feeding one synthesis), and each pinning
   its assignee's pipeline kernel (`skills=["<profile>-pipeline"]`).
2. `kanban_create` a **continuation card assigned to your own profile**
   with `parents=[the child ids]` and `skills=["researcher-pipeline"]`:
   its body says what to do with their
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
