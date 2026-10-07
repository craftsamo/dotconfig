# Execute mode — run the approved plan on its tier

- **inline** — do it now in this turn; `delegate_task` for parallel
  lookups (`../../chat-assistant/references/lookups.md`).
- **resident** — start or reuse the specialist session per
  `resident-sessions.md`. The first turn carries the SessionBrief; later
  turns carry feedback, approvals, and course corrections. Relay
  specialist questions you cannot answer within the sanctioned plan to
  the user (`clarify` when options exist); answer the rest yourself and
  note the decision in one line to the user when material.

Sequencing is conversational: when stage B consumes stage A's output,
wait for A's turn to complete (background notification), QA it, then
feed it to B. Independent stages may run as parallel resident sessions
(different keys). Start only the **frontier** — the
stages whose inputs have already passed your QA; later stages wait in the
plan. For creative media, use the selected creative Execute
entry's direct delivery and producer-check handoff instead of Assistant QA.
Required technical failures and missing approvals still block dependent use;
Writer text and all other domains retain their own acceptance gates.

## Specialists

Keep in sync with each profile's `profile.yaml` description:

This common procedure supports the selected Execute entry. The table is
navigation for a changed domain, not a loop that reloads that entry.

| Profile | Sweet spot | Capability file |
| --- | --- | --- |
| creator | Creative advisor: directions for an open look and named changes from vague feedback (consulted from execute-assistant-creative) | [execute-assistant-creative](../../execute-assistant-creative/SKILL.md) |
| image-creator / video-creator / audio-creator | Media production from filled forms | [execute-assistant-creative](../../execute-assistant-creative/SKILL.md); Client brief, scoped grants and proposal relay |
| writer | text deliverables from released units: reader-facing prose and producer-facing scripts (台本, 絵コンテ); drafts only, never publishes | [execute-assistant-writing](../../execute-assistant-writing/SKILL.md) |
| researcher | purpose-led depth proposal, agreed Build and self-check through the consuming primary; analysis, verification and guidance | [execute-assistant-research](../../execute-assistant-research/SKILL.md) |
| searcher | purpose-led retrieval proposal, agreed Build and self-check; lookups, sweeps and hunts, all resident | [execute-assistant-search](../../execute-assistant-search/SKILL.md) |
| engineer | developer using OpenCode: technical planning, implementation, independent QA and PR delivery | [execute-assistant-engineering](../../execute-assistant-engineering/SKILL.md); Client scope and explicit implementation approval; Issue management only on request |
| marketer | strategy advisor: offer discovery, positioning, campaigns, review findings and outcome analysis; never commissions parts or saves drafts | [execute-assistant-marketing](../../execute-assistant-marketing/SKILL.md): you commission, accept and save the service draft after exact remote-save consent; no publishing |

The profile is the execution contract (model, tools, standing prompt);
its pipeline skill auto-loads in every session and routes
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
