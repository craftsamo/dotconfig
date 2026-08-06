# Inline execution reference

Load when the tier is `inline` (Chat mode work). Handle the request in this
turn; no session, no card.

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
- **Medium parallel lookups** for a waiting user — `delegate_task`
  (max 3 in-turn subagents, anonymous and stateless): heavier than one
  fact, lighter than a research session.

Anything heavier — creation, deep research, code, long text — promotes to
a resident session (<Tiers> in the main skill).

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
- Job body should reference the workspace skill, resident-session flow, or
  kanban dispatch needed.
- Confirm the schedule with the user via `clarify` before registering.

## When Inline ends

Inline work has no dispatch — just respond in chat and end the turn. No
ack/notification mechanics apply.
