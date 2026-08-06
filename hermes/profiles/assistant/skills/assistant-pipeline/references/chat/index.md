# Chat mode — inline execution

Load when the request lives and dies in this turn: no dispatch, no card.
Respond and end the turn; no ack/notification mechanics apply.

## What stays in Chat

- **Conversation / emotion / opinion** — no tools, maybe the memory tool.
- **Single quick lookup** (one URL / fact / file) — light tools, deliver
  in a minute or two.
- **Workspace data ops** via the workspace skills — `workspace-ops.md`.
- **Recurring request** ("every morning …") — register a cron job —
  `cron.md`.
- **Medium parallel lookups** for a waiting user — `lookups.md`
  (`delegate_task`).

## Leaves

| Leaf | When |
| --- | --- |
| `workspace-ops.md` | people / household-budget / projects ledger ops; the sensitive-data rule |
| `cron.md` | registering or changing scheduled recurring jobs |
| `lookups.md` | in-turn parallel lookups via `delegate_task` |

## Promotion

Chat has a hard ceiling: the moment the work needs iteration, taste
feedback, or more than a few minutes of tools, stop and route through
Plan → Execute (a resident session or catalog card). Starting inline and
promoting is normal; grinding a heavy job inline is not.
