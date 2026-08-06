# Execute mode — run the approved plan on its tier

- **inline** — do it now in this turn; `delegate_task` for parallel
  lookups (`../chat/lookups.md`).
- **resident** — start or reuse the specialist session per
  `resident-sessions.md`. The first turn carries the SessionBrief; later
  turns carry feedback, approvals, and course corrections. Relay
  specialist questions you cannot answer within the sanctioned plan to
  the user (`clarify` when options exist); answer the rest yourself and
  note the decision in one line to the user when material.
- **kanban** — register a lean card per `kanban-lite.md` for the catalog
  unit named in the plan, ack with the task id, and end the turn; the
  completion notification wakes you.

Sequencing is conversational: when stage B consumes stage A's output,
wait for A's turn/card to complete (background notification), QA it, then
feed it to B. Independent stages may run as parallel resident sessions
(different keys) or parallel cards. Register only the **frontier** — the
stages whose inputs have already passed your QA; later stages wait in the
plan, not on the board.

## Specialists

Keep in sync with each profile's `profile.yaml` description:

| Profile | Sweet spot | Capability file |
| --- | --- | --- |
| creator | ALL media production: image, video, GIF, voice, music — advisories, style anchors, production, revision | `creative/index.md`; Budget grant |
| writer | text deliverables: reader-facing prose and producer-facing scripts (台本, 絵コンテ); drafts only, never publishes | `writing/index.md` |
| researcher | depth: analysis, synthesis, comparison, evaluation, verification, evidence-backed guidance | `research/index.md` |
| searcher | retrieval: targeted lookups, enumerations/surveys, exhaustive source hunts | `research/index.md` |
| engineer | implementation: drives OpenCode on a repo — code, tests, debugging, PR prep | `engineering/index.md`; Authority grant; receives the OpenCode plan-session handle |
| marketer | campaign orchestration + approved publishing (X via xurl); honest asset critique | `marketing/index.md`; Publish grant; draft-only by default |

The profile is the execution contract (model, tools, standing prompt);
its pipeline skill auto-loads in every session and card and routes
internally by deliverable — describe WHAT you need, not which internal
mode. Media never gets improvised by the assistant, whatever the tier;
text and analysis may stay inline only when genuinely light.

## Mechanics leaves

| Leaf | Owns |
| --- | --- |
| `resident-sessions.md` | wrapper commands, SessionBrief, grants, lifecycle, failure handling |
| `kanban-lite.md` | card catalog rule, card contract, wakeup triage, failures |
| `scheduled.md` | time-parked work (`scheduled` column + sweeper) |
