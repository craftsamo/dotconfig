# Hermes Agent

Self-improving AI agent CLI by Nous Research. Hermes keeps everything under
`~/.hermes/` (it does **not** read `~/.config` natively), so
[`install.sh`](../install.sh) symlinks the version-controlled, non-secret files
into place.

## Default profile symlinks

| Symlink                 | Target              |
| ----------------------- | ------------------- |
| `~/.hermes/config.yaml` | `hermes/config.yaml` |
| `~/.hermes/SOUL.md`     | `hermes/SOUL.md`    |
| `~/.hermes/mcp.json`    | `hermes/mcp.json`   |
| `~/.hermes/cron`        | `hermes/cron/`      |

Skills are **not** symlinked: `config.yaml` points `skills.external_dirs` at
`~/.config/hermes/skills`, so curated skills are read in place (read-only).
Agent-created and bundled skills stay in `~/.hermes/skills/` (untracked), which
keeps `hermes update`'s bundled-skill churn out of the repo.

## User-managed content

- `config.yaml` — model/provider, terminal backend, memory, compression,
  toolsets, `skills.external_dirs`. No secrets. Hermes rewrites this on load.
- `SOUL.md` — global agent identity (system-prompt slot #1).
- `mcp.json` — MCP server connections.
- `skills/<name>/SKILL.md` — curated, version-controlled skills.
- `cron/<job>.json` — scheduled job definitions.

## Profiles

Named profiles map the same way under `~/.hermes/profiles/<name>/`. To track a
profile:

1. `hermes profile create <name>` — seeds state + the `~/.local/bin/<name>` alias.
2. Add `hermes/profiles/<name>/{config.yaml,SOUL.md,mcp.json,skills/,cron/}`.
3. Point that profile's `skills.external_dirs` at
   `~/.config/hermes/profiles/<name>/skills`.
4. Re-run `./install.sh` — the `[hermes]` loop overlays the tracked files.

## Secrets

No `.env` files. API keys live in the macOS Keychain and are injected at launch
by the [`bin/hermes`](../bin/secret-shim) secret-shim (`secret env -p global`
then `secret env -p hermes`). Shared keys (e.g. `OPENROUTER_API_KEY`) go in the
`global` layer; Hermes-only keys (e.g. `TELEGRAM_BOT_TOKEN`, `FAL_KEY`,
`BROWSERBASE_API_KEY`) go in the `hermes` layer. See
[`secret`](../zsh/functions/secret.md).

## Installing the binary

Outside the [Brewfile](../Brewfile). Prefer clone + `./setup-hermes.sh` (lands
in `~/.local/bin/hermes`, already on `PATH` behind the shim). Avoid the
`curl … | bash` installer — it edits shell rc files, and `~/.zshrc` is a symlink
into this repo.

## Never tracked

Per-machine state stays in `~/.hermes/`: `.env`, `auth.json`, `memories/`,
`sessions/`, `state.db*`, `logs/`, `workspace/`, `plans/`, `*_cache/`, `local/`.
