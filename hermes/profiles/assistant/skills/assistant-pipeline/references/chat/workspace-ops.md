# Workspace data ops

Operate the personal/project ledgers inline via the workspace skills:

- `people` (`pp`) — people ledger
- `household-budget` (`hb`) — budget/ledger
- `projects` (`pj`) — project registry

## Sensitive data rule

Personal data (`~/Workspaces/Personal/<Group>/`) is sensitive:

- Summarize; never paste raw values, balances, account numbers, holdings,
  or personal identifiers into chat or logs.
- No external sends, uploads, or third-party API calls with this data
  without an explicit, specific OK from the user.
- Read + compute locally; write outputs to the owning
  `~/Workspaces/Personal/<Group>/.agent/deliverables/<job>/` and return a
  summary. Use the root `.deliverables/` fallback only when no single
  Personal Group owns the output.
