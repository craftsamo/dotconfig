# Personal — data & automation (no git, grouped)

Each subdirectory is a **group** (topic, e.g. a people ledger). No code repos here
(`Projects/` holds all git-managed code). A group holds:
- `data/` — data files (e.g. `data/*.json`). **Sensitive.**
- `docs/` — notes / docs.

## Data-handling rules (strict)
- Treat contents as sensitive: summarize; never paste raw values, balances, account
  numbers, holdings, or personal identifiers into chat or logs.
- No external sends, uploads, or third-party API calls with this data without an
  explicit, specific OK from the human.
- Read + compute locally; write outputs to `../.deliverables/` and return a summary.
- Don't `git init` here — Personal is intentionally untracked, local-only.

Add a group with `workspace-scaffold`: `ws-new.sh group personal <Group>`.
