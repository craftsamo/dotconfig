# Personal — data, automation, registries (no git)

No code repos here (`Projects/` holds all git-managed code). Layout:
- `data/` — personal data (budgets, exports, …). **Sensitive.**
- `docs/` — personal notes / docs.
- `Peoples/` — people ledger as `*.json` (referenced by team workflows).

## Data-handling rules (strict)
- Treat contents as sensitive: summarize; never paste raw values, balances, account
  numbers, holdings, or personal identifiers into chat or logs.
- No external sends, uploads, or third-party API calls with this data without an
  explicit, specific OK from the human.
- Read + compute locally; write outputs to `../.deliverables/` and return a summary,
  not the raw file, unless asked.
- Don't `git init` here — Personal is intentionally untracked, local-only.
