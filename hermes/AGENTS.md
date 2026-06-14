# hermes/ — maintainer rules (for OpenCode)

Version-controlled, non-secret **Hermes Agent** config. `../install.sh` symlinks
these into `~/.hermes/`; Hermes reads `~/.hermes/`, never `~/.config`. This file
is guidance for the agent maintaining this subtree — **not** Hermes runtime config.
Authoritative depth: `README.md` (mechanics) and `PROFILES.md` (multi-agent design).

## Critical rules

- **Edit here, never `~/.hermes/…`.** Those are symlinks back to this repo. New
  files need `../install.sh` to link them; `link()` never overwrites a real file
  (prints `WARN … not overwriting` and skips). Adopt existing real files via the
  move-then-`install.sh` steps in `README.md`.
- **No secrets, no `.env`.** Keys live in the macOS Keychain, injected by the
  `bin/hermes` shim. See the `keychain-secrets` skill / `opencode/instructions/secrets.md`.
- **`config.yaml` is rewritten by Hermes on load.** Expect re-serialization churn;
  match Hermes' output format (block style, key order), keep diffs minimal — don't
  hand-reformat or alphabetize.
- **`SOUL.md` = persona only** (voice/posture), per-profile (`HERMES_HOME`). No
  project rules/paths/commands there. Headings aren't parsed (verbatim inject).
- **Keep `default` neutral** — every `--clone` inherits its `config.yaml`.
  Specialized personas, bots, and cron belong in named profiles.
- **OAuth logins from `default` only** (`hermes model`, no `-p`). Codex / Copilot /
  xAI creds are inherited read-only by every profile; running `hermes model` inside
  a worker writes that profile's `auth.json` and shadows the inherited creds.
- **Operating policy lives in `agent.system_prompt`** (per-profile, always-on);
  detailed playbooks are per-profile skills. `SOUL.md` stays persona-only. Do **not**
  run `/personality` on a profile — it shares the `agent.system_prompt` slot and
  silently overwrites the operating contract (the messaging assistant is most at risk).

## Layout

```
config.yaml          # model/providers, toolsets, agent settings (Hermes-rewritten)
SOUL.md              # default persona (prompt slot #1)
mcp.json             # MCP servers ({} = none)
cron/                # jobs.json tracked; output/ + .tick.lock ignored
skills/              # agent-created skills tracked; .hub/ etc. ignored
launchd/             # assistant gateway LaunchAgent (template + launcher)
profiles/<name>/     # assistant, coder, researcher, searcher
  - config.yaml      # model/fallback + agent.system_prompt (operating contract)
  - profile.yaml     # routing description (kanban/delegation)
  - SOUL.md          # per-profile persona (BASE + role posture)
  - skills/          # per-profile skills (opencode-loop / research-pipeline / breadth-retrieval)
  - cron/            # per-profile scheduled jobs (jobs.json; placeholder if empty)
setup.sh README.md PROFILES.md
```

## Profiles

default (CLI driver/orchestrator) + assistant (messaging front door, hosts the
gateway/dispatcher) + coder / researcher / searcher (kanban workers). Tracked per
profile: `config.yaml`, `profile.yaml`, `SOUL.md`, `skills/`, `.no-bundled-skills`.
Create with `hermes profile create <name> --description "…"`, then adopt into the
repo (move real files → `../install.sh`); see `README.md` / `PROFILES.md`.

## Tracked vs ignored

Tracked: config / SOUL / `profile.yaml`, agent-created skills, `cron/jobs.json`,
`launchd/`, docs. Ignored (see `../.gitignore`): `auth.json`, `.env`, `memories/`,
`sessions/`, `state.db*`, `logs/`, `workspace/`, `.hub/`, `.curator_state`,
`.usage*`, `cron/output/`. Never commit secrets, state, or host-rendered plists.

## Commands

- `./setup.sh` — install/refresh the hermes binary (uv venv); idempotent.
- `../install.sh` — create the `~/.hermes/` symlinks (run after adding files).
- `hermes update` — git pull + re-sync (use this to update, not setup.sh).
- `hermes doctor` — validate providers / model tiers.
- `launchd/gateway-launchctl.sh {install,status,uninstall}` — gateway LaunchAgent,
  **one host only** (one bot token = one live connection). Telegram-only for now
  (workaround for upstream #40695; don't re-enable Discord until fixed).

## Commits

Conventional Commits with the `(hermes)` scope: `feat(hermes): …`,
`chore(hermes): …`, `docs(hermes): …`, `refactor(hermes): …`.
