# Delegate engine — fan-out to producer workers

Shared engine, loaded by any mode that hands work to another worker. The
marketer orchestrates; it does not produce long prose (writer), media
(creator), or research (searcher/researcher). This file owns the mechanics:
when to fan out, how to write child briefs, and how results come back.

## When to fan out (vs doing it in-turn)

- `delegate_task` — quick parallel lookups you can wait out inside one run
  (a fact check, a handful of sources). Nothing durable.
- **Board fan-out** (below) — anything heavier or durable: an asset, article
  copy, a market scan. Never wait in-process for a child card.
- Neither — short-form post copy, thread breakdowns, hooks: that assembly
  is the marketer's own hands, always.

## Board fan-out (continuation-card pattern)

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread),
   and each pinning its assignee's pipeline kernel
   (`skills=["<profile>-pipeline"]`).
2. `kanban_create` a **continuation card assigned to your own profile** with
   `parents=[the child ids]` and `skills=["marketer-pipeline"]`: its body
   says what to do with their results
   (their completion summaries/metadata arrive in the injected context;
   `kanban_show` a parent id for detail). It is a bookmark for a future run
   of you — that run starts with zero memory of this one, so the body must
   stand alone: restate the brief, the effective Publish grant, and the
   acceptance bar the results must clear.
3. `kanban_complete` the current card ("decomposed into <ids>") and stop —
   the dispatcher wakes the continuation card when all children finish
   (fan-in). Record dispatched child ids in a `PROGRESS:` comment first.

## Child briefs per worker

Child bodies carry a full brief — workers never see your context:

- **writer** — long copy, article-length text, tone-sensitive wording. Pass
  the WritingBrief fields: audience, purpose, medium, tone, length, and the
  facts allowed (from your MarketingBrief — never let a child invent
  claims).
- **creator** — images/video/GIF. Pass a full MediaBrief + destination
  specs (X: 16:9 or 1:1, alt text; name the exact deliverable files
  expected back as attachments).
- **searcher/researcher** — market/competitor/trend input you lack. Scope
  the question tightly; a searcher sweep and a researcher synthesis are
  different cards.

## Rules

- **Grants never propagate.** Child bodies carry NO `Publish:` line, ever —
  children produce drafts and research, they never publish. A child that
  would need any grant is a question for the orchestrator: block on YOUR
  card, don't mint.
- Children you create notify nobody (no chat subscription); the
  orphan-watchdog cron is the safety net, not a license. Decisions that
  need the user go through your own card's block round-trip, never a
  child's.
- **Consume, don't re-produce.** On fan-in, read the children's final
  messages and attachments; verify every attachment exists before
  referencing it. Rejecting a deliverable is normal — say why against the
  brief and either re-dispatch with a corrected brief or escalate.

## Pitfalls

- Waiting in-process for a child card instead of completing with a
  continuation card.
- A continuation-card body that assumes memory of this run — it has none.
- Granting a child publishing authority, or a wider grant than your own.
- Re-producing locally what a child already delivered (or referencing an
  attachment you never verified).

## Verification

- Every dispatched child id is recorded in a `PROGRESS:` comment.
- Continuation card exists with `parents` set and a self-contained body
  (brief + effective grant + acceptance bar restated).
- No child body carries a Publish grant.
