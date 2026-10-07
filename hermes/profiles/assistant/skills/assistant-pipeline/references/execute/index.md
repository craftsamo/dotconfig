# Execute mode — run the approved plan on its tier

- **inline** — do it now in this turn; `delegate_task` for parallel
  lookups (`../../chat-assistant/references/lookups.md`).
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
plan, not on the board. For creative media, use the selected creative Execute
entry's direct delivery and producer-check handoff instead of Assistant QA.
Required technical failures and missing approvals still block dependent use;
Writer text and all other domains retain their own acceptance gates.

## Specialists

Keep in sync with each profile's `profile.yaml` description:

This common procedure supports the selected Execute entry. The table is
navigation for a changed domain, not a loop that reloads that entry.

| Profile | Sweet spot | Capability file |
| --- | --- | --- |
| creator | Media consultation, production, revision and analysis; coordinates production dependencies | [execute-assistant-creative](../../execute-assistant-creative/SKILL.md); Client brief, scoped grants and proposal relay; unit decomposition only for confirmed legacy work |
| writer | text deliverables from released units: reader-facing prose and producer-facing scripts (台本, 絵コンテ); drafts only, never publishes | [execute-assistant-writing](../../execute-assistant-writing/SKILL.md) |
| researcher | purpose-led depth proposal, agreed Build and self-check through the consuming primary; analysis, verification and guidance | [execute-assistant-research](../../execute-assistant-research/SKILL.md) |
| searcher | purpose-led retrieval proposal, agreed Build and self-check; lookups, sweeps and hunts, with settled cards unchanged | [execute-assistant-search](../../execute-assistant-search/SKILL.md) |
| engineer | developer using OpenCode: technical planning, implementation, independent QA and PR delivery | [execute-assistant-engineering](../../execute-assistant-engineering/SKILL.md); Client scope and explicit implementation approval; Issue management only on request |
| marketer | strategy advisor: offer discovery, positioning, campaigns, review findings and outcome analysis; never commissions parts or saves drafts | [execute-assistant-marketing](../../execute-assistant-marketing/SKILL.md): you commission, accept and save the service draft after exact remote-save consent; no publishing |

The profile is the execution contract (model, tools, standing prompt);
its pipeline skill auto-loads in every session and card and routes
internally by its own contract — describe WHAT you need, not which internal
mode. Media never gets improvised by the assistant, whatever the tier;
text and analysis may stay inline only when genuinely light.

Researcher/Searcher select their own Plan, Build and QA phases; these are not
new Assistant menu entries or external roots. Purpose-first sessions start Plan,
then Client agreement releases Build and specialist self-check before requester
independent acceptance. Explicitly authorized settled briefs may enter Build
directly. Keep proposal/approval messages in the existing work conversation;
transport kind and filled fields alone grant nothing. A bounded authorized
researcher inquiry may be one-shot through the consuming primary; complex
back-and-forth stays resident. No direct Assistant-to-Researcher route is added.

## Mechanics leaves

| Leaf | Owns |
| --- | --- |
| `resident-sessions.md` | wrapper commands, SessionBrief, grants, lifecycle, failure handling |
| `kanban-lite.md` | card catalog rule, card contract, wakeup triage, failures |
| `scheduled.md` | time-parked work (`scheduled` column + sweeper) |
