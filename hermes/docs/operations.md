# Gateway, tracking and status

Gateway as a persistent service, what is tracked, and the current state. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Gateway as a persistent service

The **default** profile hosts ONE multiplex gateway (with the embedded kanban
dispatcher, `dispatch_interval_seconds: 15`) keychain-pure via a
**LaunchAgent**: `gateway.multiplex_profiles: true` + the allowlist (assistant,
engineer, creator, marketer, writer, researcher, image-creator, video-creator,
audio-creator) in the root `config.yaml` make that single process connect every
served profile's enabled platforms — assistant Telegram (+ topics) and Discord,
the engineer / creator / marketer Telegram bots, and the A2A endpoints on
127.0.0.1:9902-9909. Secondary profiles never run their own gateway. Three
tracked, machine-agnostic files in `hermes/launchd/`:

- **`hermes-gateway-multiplex`** — the launcher. Sets its own `PATH` (a
  LaunchAgent can start with a stripped one), `cd`s to `~/Workspaces`, logs to
  `~/.hermes/logs/gateway-multiplex.log`, `eval`s the `global` + `hermes`
  Keychain layers (minus messaging keys) into the process env for raw-env
  readers and subprocess inheritance — the scope-aware keys come per profile
  from `secrets.command` (see [`models-auth.md`](./models-auth.md) "Secrets
  layering") — re-syncs the Brave clone, then execs `hermes gateway run` (no
  `-p` — default is the multiplex host). Every path is `$HOME`-relative; no
  `.env`. (`secret env` has **no `-- <cmd>` form**, hence the `eval`.) It
  exports no `HERMES_PROFILE`: one process serves many profiles.
- **`local.hermes.gateway.multiplex.plist.tmpl`** — LaunchAgent template with a
  `__HOME__` placeholder (launchd can't expand `~`). Runs the launcher as
  `ProgramArguments[0]`, so the login item reads `hermes-gateway-multiplex`, not
  `sh`.
- **`gateway-launchctl.sh`** — renders the template (`__HOME__` → `$HOME`) into
  `~/Library/LaunchAgents/` (host-local, never committed) and loads it; on
  install it also unloads the legacy `local.hermes.gateway.assistant` agent so
  two pollers never race one bot token.

**Telegram + Discord.** Gateway DB calls run off the asyncio loop
(`AsyncSessionDB` / `asyncio.to_thread`, upstream #40695) with dedicated
regression tests — synchronous SQLite access from `_handoff_watcher` stalls
Discord heartbeats and the dispatcher — so the launcher exposes both platform
credentials. Keep the Discord toolset granular and equal to Telegram; never
replace either list with a broad bundled toolset.

Discord is limited to the private config's user and channel allowlists. A channel
mention creates a thread; the parent channel's `assistant-pipeline` binding and
prompt carry into that thread. Live voice uses `/voice join` and the existing
STT/TTS fallback chains. It leaves after five idle minutes by default, and a
gateway restart requires a manual rejoin. Cron/system Inbox delivery stays on
Telegram to avoid duplicate proactive notifications.

**Per-profile tool resolution.** In one multiplex process, toolset resolution
must be memoized per profile scope as well as per registry generation (carried
as a local patch) — otherwise warming one profile's `tts` entry hides
scope-registered tools such as character-voice from another.
`test_audio_creator_routing.py` exercises the real resolver across scopes;
registration-only tests and direct CLI synthesis cannot detect this
gateway-specific failure.

Activate on the **gateway host only** (one bot token = one live connection —
four bots means four tokens, all owned by this one process; stop any gateway
elsewhere first):

```
hermes/launchd/gateway-launchctl.sh install      # render template + load
hermes/launchd/gateway-launchctl.sh status        # check
hermes/launchd/gateway-launchctl.sh uninstall      # unload + remove
```

## Tracking

Per-profile, tracked in `hermes/profiles/<name>/` and symlinked by
`install.sh`: `config.yaml`, `profile.yaml` (holds the routing `description`),
`SOUL.md`, `skills/`, `.no-bundled-skills` (`mcp.json` when present). `cron/`
is never linked or tracked — Hermes owns it machine-local. Everything outside
the symlink set stays untracked (`~/.hermes/kanban.db`, `kanban/`,
`workspace/`, `auth.json`, `.env`, `memories/`, `sessions/`, `state.db*`);
adoption steps are in [`README.md`](../README.md#tracking-a-profile).

Routing quality depends on `profile.yaml` descriptions — create workers with
`hermes profile create <name> --description "<role>"` (or
`hermes profile describe <name> --text "…"`).

## Current state

| Component | State | Documented in |
| --- | --- | --- |
| Multiplex gateway (4 Telegram bots, assistant Discord, A2A endpoints, dispatcher) | deployed, one host | "Gateway as a persistent service" above; [`topology.md`](./topology.md) "Topology" |
| A2A peer graph (`a2a_agents`, `timeout: 310`) | deployed; peer-list enforcement is config + operating contract, not a plugin hook | [`topology.md`](./topology.md) "Topology" |
| Resident sessions + lean kanban board (fire-and-forget / cron / mass-parallel / `scheduled`) | deployed; a real short-video production run through this flow is still unverified; direction is a stepwise move toward flatter, equal-primary operation | [`topology.md`](./topology.md) "Three delegation layers" |
| Per-profile secret scopes | deployed | [`models-auth.md`](./models-auth.md) "Secrets layering" |
| Model chains | deployed; probed per provider/model, per-profile behavior unevaluated | [`models-auth.md`](./models-auth.md) "Models and fallback chains" |
| Creator hands (v3) | in progress, family by family | [`hands/overview.md`](./hands/overview.md) "Migration" |
| Role-entry candidates (Engineer v9, Researcher/Searcher entries, Writer v8, Creative early delivery) | candidates, not deployed; cutover needs explicit approval, a controlled gateway restart and fresh sessions | [`profiles/`](./profiles/) per role |
