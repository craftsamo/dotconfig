# Workspace data ops

Operate the personal/project ledgers inline via the workspace skills:

- the workspace registry — people, projects, memberships and repos — through the
  `workspace_registry` tool (data: `~/Workspaces/.registry/*.csv`)
- `household-budget` (`hb`) — budget/ledger

## Sensitive data rule

Personal data (`~/Workspaces/Personal/<Group>/`) is sensitive:

- Summarize; never paste raw values, balances, account numbers, holdings,
  or personal identifiers into chat or logs.
- No external sends, uploads, or third-party API calls with this data
  without an explicit, specific OK from the user.
- Read + compute locally; write outputs to the owning
  `~/Workspaces/Personal/<Group>/.agent/<YYYYMMDD>-<job>/` draft and return a
  summary. Use the root `~/Workspaces/.agent/` only when no single
  Personal Group owns the output.
