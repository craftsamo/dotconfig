# Script / CLI / automation — plan recipe

The smallest deliverable class; ceremony is the enemy. Most tools are
settled enough to skip the base session (index invariant) — use one
only when the tool has real architecture (multiple commands, external
services, scheduled operation).

## Brief — fix before the session

- **Contract** — input → output, one line each; failure behavior.
- **Runtime & where it runs** — Python/Node/shell; manual, cron,
  launchd, or called by Hermes. A worker-executed script must obey the
  approval guard: no inline interpreters, wrap logic in files.
- **Data touched** — paths, APIs, credentials (Keychain), and whether
  anything is sensitive (`Personal/` rules apply).
- **Repo or not** — durable tool → github-first repo like everything
  else (bootstrap, usually scratch — starters rarely fit); throwaway →
  `.scratch/`, no repo, no ceremony.
- **Done criteria** — runs on real input, exits nonzero on failure.

## Wave prompt — only when a session is warranted

> Small tool. Expect 1–3 Waves: working core against real input →
> hardening (errors, edge cases) → wiring (cron/launchd/docs). No
> speculative features.

## Expected decomposition — inspection standard

- 1–3 Waves; core-first, wiring last.
- Red flags: frameworks or plugin systems for a script; config
  abstraction the Brief never asked for; missing "run on real input"
  verification.

## Defaults

- New repo: scratch (no starter) via `bootstrap.md` first; skip repo
  entirely for throwaways.
- Authority `A1`; dependency additions need `A3` even here.
- Verification: execute on real input and inspect output + exit code;
  for scheduled tools, one observed scheduled run.
