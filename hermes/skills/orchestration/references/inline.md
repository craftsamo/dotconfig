# Inline execution reference

Load when <RequirementAndShape> selects `inline`. Handle the request in chat;
do not register a card.

## When to pick Inline

- **Conversation / emotion / opinion** — no tools, maybe the memory tool.
- **Single quick lookup** (one URL / fact / file) — light tools, deliver
  in a minute or two.
- **Workspace data ops** — via the workspace skills:
  - `people` (`pp`) — people ledger
  - `household-budget` (`hb`) — budget/ledger
  - `projects` (`pj`) — project registry
- **Recurring request** ("every morning …") — register a cron job (see
  below).

If the user is actively waiting on a **medium** parallel lookup that's
heavier than a single fact but lighter than a board job, `delegate_task`
(in-turn subagents) is the exception — fire parallel lookups inline. For
anything heavier, select `single`, `chain`, or `planned`.

## Workspace data ops — sensitive data rule

Personal data (`~/Workspaces/Personal/<Group>/`) is sensitive:

- Summarize; never paste raw values, balances, account numbers, holdings,
  or personal identifiers into chat or logs.
- No external sends, uploads, or third-party API calls with this data
  without an explicit, specific OK from the user.
- Read + compute locally; write outputs to `~/Workspaces/.deliverables/`
  and return a summary.

## Recurring requests — cron registration

For "every morning do X", "weekly digest of Y", register a cron job:

- Use the appropriate profile's cron (`hermes/profiles/<name>/cron/jobs.json`).
- Most recurring jobs belong on `assistant` (which hosts the gateway and
  runs cron continuously).
- Job body should reference the workspace skill or worker dispatch needed.
- Confirm the schedule with the user via `clarify` before registering.

## When Inline ends

Inline work has no dispatch — just respond in chat and end the turn. No
ack/notification mechanics apply.
