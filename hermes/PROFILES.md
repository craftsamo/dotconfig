# Profiles — multi-agent plan

How this machine runs several Hermes agents that cooperate: two **front
doors** a human talks to, plus named **worker** profiles they delegate to in
the background. This is the design doc; [`README.md`](./README.md) covers the
single-profile mechanics (symlinks, skills, cron, secrets).

A profile is just a separate `HERMES_HOME` (`~/.hermes/profiles/<name>/`) with
its own `config.yaml` / `.env` / `SOUL.md` / `skills/` / `cron/` / state, and a
`~/.local/bin/<name>` alias that runs `hermes -p <name>`. The default profile is
`~/.hermes` itself (it can't be deleted or renamed).

## Topology

```
   human (terminal)            human (Discord / Telegram)
          │                              │
        default ──┐                  assistant ──┐   (runs the gateway + kanban dispatcher)
        (CLI)     │                (~/Workspaces)│
                  │                              │
                  └──────────┬───────────────────┘
                             │ create kanban tasks
                             ▼
                 ~/.hermes/kanban.db  (one shared board)
                             │ dispatcher (in assistant's gateway) spawns
              ┌──────────────┼──────────────┐
              ▼              ▼               ▼
           searcher      researcher        coder
          (retrieve)    (synthesize)     (implement)
```

Verified against the source clone
(`~/ghq/github.com/NousResearch/hermes-agent`):

- **One shared board.** The kanban DB is anchored at the base
  `~/.hermes/kanban.db` via `get_default_hermes_root()` — *not* profile-scoped
  (`kanban_db.py:264-284,429-431`). Every profile reads/writes the same board.
- **One gateway powers everything.** The dispatcher runs inside the gateway and
  sweeps **all** boards each tick, regardless of which profile the gateway runs
  as (`gateway/kanban_watchers.py:861-867`). So `assistant`'s gateway dispatches
  tasks created by `default`'s CLI. `default` needs no gateway of its own.
- **Workers are spawned through the PATH `hermes`.** The dispatcher launches
  `hermes -p <worker> … chat -q "work kanban task <id>"` as a subprocess,
  resolving `hermes` via `shutil.which` (so our `bin/hermes` shim is used) and
  inheriting a copy of the gateway's env with `HERMES_HOME` overridden
  (`kanban_db.py:6705-6837,6607`). Workers therefore get the `global` + `hermes`
  Keychain layers injected automatically — **no per-worker secret is needed.**

## Two delegation layers

| | Kanban | `delegate_task` |
| --- | --- | --- |
| Worker | **named profile** (coder/researcher/searcher) | anonymous subagent |
| Durability | persistent queue, resumable, human-in-loop | synchronous, dies with the turn |
| Requires | a running gateway (the dispatcher) | nothing — fires automatically |
| Use for | cross-agent / long / auditable work | in-turn parallel research or refactor |

**Fallback story:** gateway up → durable named-worker delegation via Kanban.
Gateway down → `default` still parallelizes via `delegate_task` (anonymous,
in-turn). A Kanban worker may itself call `delegate_task` during its run.

## Profile roster

| Profile | Role | Front door | `terminal.cwd` | Toolsets | Gateway | Tracked |
| --- | --- | --- | --- | --- | --- | --- |
| **default** | general daily driver + orchestrator | CLI | `.` (launch dir) | full + `kanban` | — | yes |
| **assistant** | messaging front door + dispatcher host | Discord/TG | `~/Workspaces` | full + `kanban` | **yes** | yes (token per-machine) |
| **coder** | implement (git worktree, run tests) | — (worker) | `.` (launch / task ws) | `hermes-cli` | — | yes |
| **researcher** | synthesize / analyze | — (worker) | `.` (launch / task ws) | `file,web` | — | yes |
| **searcher** | fast retrieval (web / x_search) | — (worker) | `.` (launch / task ws) | `web,x_search` | — | yes |

Role split: **searcher (retrieve) → researcher (synthesize) → coder
(implement)**, mirroring the `delegate_task` toolset patterns
(`["web"]` / `["file","web"]` / `["terminal","file"]`).

### Default is a clean baseline, not a junk drawer

Keep default's `config.yaml` rich (every `--clone` inherits it) and its
`SOUL.md` neutral; keep its `cron/` empty and run no gateway on it. Specialized
personas, bots, and scheduled automation belong in named profiles. Workers fan
out via Kanban; default just orchestrates and does interactive work.

### Two working directories per worker

- **Kanban-dispatched work** runs in the task workspace
  (`$HERMES_KANBAN_WORKSPACE`): `worktree:` for coder (isolated + preserved),
  `scratch` for the rest (ephemeral, deleted on completion).
- **Direct / `delegate_task` work** starts in `terminal.cwd` — currently `.`
  (the launch dir) for every worker; pin an absolute path per worker if you want
  a fixed directory. `workspace/` is per-machine and never tracked.

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2-3). `fallback_providers` is **per-turn**: it triggers on errors
(429 / 5xx / 401 / 404 / malformed) and the primary is restored on the next
turn. The default profile already proves the YAML shape.

| Profile | T1 (primary) | T2 | T3 |
| --- | --- | --- | --- |
| **default** | `openai-codex` / gpt-5.5 | `copilot` / gpt-5.5 | `openrouter` / `xiaomi/mimo-v2.5` |
| **assistant** | `openai-codex` / gpt-5.5 | `copilot` / gpt-5.5 | `openrouter` / `xiaomi/mimo-v2.5` |
| **coder** | `openai-codex` / gpt-5.5 | `copilot` / gpt-5.5 | `openrouter` / `xiaomi/mimo-v2.5` |
| **researcher** | `xai-oauth` / grok-4.3 | `copilot` / claude-sonnet-4.6 | `openrouter` / `deepseek/deepseek-v4-flash` |
| **searcher** | `xai-oauth` / grok-4.3 | `copilot` / gpt-5.5 | `openrouter` / `google/gemini-3.5-flash` |

```yaml
# example — researcher's ~/.hermes/profiles/researcher/config.yaml
model:
  default: grok-4.3
  provider: xai-oauth
  base_url: https://api.x.ai/v1
fallback_providers:
  - provider: copilot
    model: claude-sonnet-4.6
  - provider: openrouter
    model: deepseek/deepseek-v4-flash
    base_url: https://openrouter.ai/api/v1
    api_mode: chat_completions
```

Model facts confirmed during the build (live `provider_models_cache.json` + test
calls):

- **Grok** — `grok-4.3` is current on `xai-oauth` and verified working (the
  retired `grok-4*` glob doesn't cover it; re-auth via `hermes model` if the
  token lapses). `x-ai/grok-4.3` is the OpenRouter equivalent for per-token use.
- **Copilot has no Grok** — its catalog is Claude + GPT-5.x + gemini-2.5-pro, so
  worker T2 uses `claude-sonnet-4.6` (researcher) / `gpt-5.5` (searcher).
- **OpenRouter slugs** — `xiaomi/mimo-v2.5`, `deepseek/deepseek-v4-flash`,
  `google/gemini-3.5-flash` (the earlier `*-v3.2` / `gemini-3-flash-preview`
  refs were planning guesses).

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

## Authentication inheritance

`auth.json` is per-profile (`auth.py:855-856`, built from `get_hermes_home()`),
**but** a named profile with no entry for a provider falls back **read-only** to
the default profile's `~/.hermes/auth.json` (`auth.py:1131-1157,1215-1259`).

- OAuth logins done in **default** (`hermes model`, no `-p`) — Codex, Copilot,
  xAI-OAuth — are inherited by every worker. **No per-worker re-auth.**
- Always run OAuth logins from default. Running `hermes model` *inside* a worker
  writes that profile's `auth.json` and shadows the inherited creds for that
  provider (writes never propagate).
- Env tokens work everywhere via the shim: Copilot reads
  `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth token`
  (`copilot_auth.py:39,67-95`); xAI accepts `XAI_API_KEY`.

Two caveats:

1. **Copilot token shadowing.** Copilot checks env before stored OAuth creds
   (`COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh`). The current
   `hermes`-layer `GITHUB_TOKEN` is already Copilot-capable (verified with a live
   `--provider copilot` call), so this is fine — but if you swap it for a classic
   `ghp_*` token, Copilot 401s. Then set a Copilot-capable
   **`COPILOT_GITHUB_TOKEN`** (highest priority) so it wins regardless.
2. **Parallel OAuth refresh.** Several workers refreshing the same rotating
   refresh token at once can race to `invalid_grant`. If it bites, move
   high-parallelism workers' T1 to an API-key provider (OpenRouter / `XAI_API_KEY`).

## Secrets layering

No `.env`. The `bin/hermes` shim injects two Keychain layers at launch —
`global` (shared by every shimmed tool) then `hermes` (the command name). A
profile alias `~/.local/bin/<name>` runs **bare `hermes -p <name>`**, so it
routes through the same `bin/hermes` shim — **every profile gets `global` +
`hermes`** (`~/.config/bin` precedes `~/.local/bin` on `PATH`). See
[`README.md`](./README.md#secrets).

- **`hermes`** — shared model/fallback keys every profile and every
  dispatcher-spawned worker needs: `OPENROUTER_API_KEY` (T3) and a
  Copilot-capable `GITHUB_TOKEN` (the `copilot` T2 + Skills Hub).
- **`global`** — keys shared with *other* tools (editor, MCP servers, other
  CLIs). Nothing Hermes-specific needs to live here.
- **gateway secrets** (`DISCORD_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, +
  `*_ALLOWED_USERS` / `*_HOME_CHANNEL`) currently sit in the **`hermes`** layer,
  so the shim injects them whenever the gateway runs. Move them to a dedicated
  `assistant` layer if you want them off non-gateway profiles.
- **OAuth** (default's `auth.json`): Codex / Copilot / xAI-OAuth, inherited by
  every profile (read-only fallback).

Workers need no unique secret: the dispatcher execs `hermes -p <worker>`, which
hits the `bin/hermes` shim (`global` + `hermes`), and they also inherit the
gateway's env. A background **LaunchAgent** can start with a stripped `PATH`, so
the assistant launcher sets its own `PATH` and `eval`s the Keychain layers
directly (below).

## Gateway as a persistent service

Assistant hosts the gateway (and the embedded kanban dispatcher) keychain-pure
via a **LaunchAgent**. Three tracked, machine-agnostic files in `hermes/launchd/`:

- **`hermes-gateway-assistant`** — the launcher. Sets `PATH`, `cd`s to
  `~/Workspaces`, logs to `~/.hermes/logs/gateway-assistant.log`, `eval`s the
  `global` + `hermes` Keychain layers (`TELEGRAM_BOT_TOKEN` /
  `OPENROUTER_API_KEY` / `GITHUB_TOKEN` / …) like the shim does, then execs the
  real `hermes -p assistant gateway run`. Every path is `$HOME`-relative — no
  hardcoded home, no `.env`. (`secret env` has **no `-- <cmd>` form**, hence the
  `eval`.)
- **`local.hermes.gateway.assistant.plist.tmpl`** — LaunchAgent template with a
  `__HOME__` placeholder (launchd can't expand `~`). Runs the launcher as
  `ProgramArguments[0]`, so the login item reads `hermes-gateway-assistant`, not
  `sh`.
- **`gateway-launchctl.sh`** — renders the template (`__HOME__` → `$HOME`) into
  `~/Library/LaunchAgents/` (host-local, never committed) and loads it.

**Telegram-only — workaround for upstream #40695.** With Discord connected the
gateway's `_handoff_watcher` blocks the event loop on a `list_pending_handoffs`
SQLite query and hangs (discord heartbeat stalls, dispatcher stops). The launcher
`unset`s `DISCORD_*` so only Telegram runs — verified stable, with the embedded
dispatcher auto-claiming tasks across ticks. Re-enable Discord (drop the `unset`
line) once the bug is fixed.

Activate on the **gateway host only** (one bot token = one live connection — stop
any gateway elsewhere first):

```
hermes/launchd/gateway-launchctl.sh install      # render template + load
hermes/launchd/gateway-launchctl.sh status        # check
hermes/launchd/gateway-launchctl.sh uninstall      # unload + remove
```

## Tracking

Per-profile, tracked in `hermes/profiles/<name>/` and symlinked by
`install.sh`: `config.yaml`, `SOUL.md`, `skills/`, `.no-bundled-skills`, and
**`profile.yaml`** (holds the routing `description`).

- **`install.sh`** links `config.yaml` / `profile.yaml` / `SOUL.md` / `skills/`
  / `.no-bundled-skills` per profile (`mcp.json` / `cron/` when present).
- `cron/` is tracked only where automation lives (assistant, if any).
- Auto-untracked (outside the symlink set): `~/.hermes/kanban.db`, `kanban/`,
  `workspace/`, `auth.json`, `.env`, `memories/`, `sessions/`, `state.db*`.

Routing quality depends on `profile.yaml` descriptions — create workers with
`hermes profile create <name> --description "<role>"` (or
`hermes profile describe <name> --text "…"`).

## Status (as-built)

Built and verified: default (kanban orchestrator), coder, researcher, and searcher
workers — T1–T3 tiers resolve (doctor + live probes) and default-created tasks
dispatch/route to each. Assistant gateway runs keychain-pure (LaunchAgent,
Telegram-only per #40695); the embedded dispatcher auto-claims tasks across ticks.
`install.sh` links every tracked profile (incl. `profile.yaml`) with no WARN.

Model slugs confirmed live: `grok-4.3` on `xai-oauth`, `claude-sonnet-4.6` (worker
T2), `deepseek/deepseek-v4-flash`, `google/gemini-3.5-flash`; Copilot has no Grok.

Remaining (manual): Telegram round-trip — message the bot and confirm a reply.
