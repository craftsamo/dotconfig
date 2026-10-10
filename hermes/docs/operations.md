# Gateway and tracking

How the multiplex gateway runs as a LaunchAgent and which per-profile files are tracked. Read it before changing the launcher, the plist or the symlink set. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Gateway as a persistent service

The **default** profile hosts the ONE multiplex gateway keychain-pure via a
**LaunchAgent**; which profiles and A2A ports it serves is in
[`topology.md`](./topology.md) "Multiplex gateway and A2A peer graph".
Secondary profiles never run their own gateway (never use
`hermes -p <name> gateway stop` on a role that must stay reachable). Three
tracked, machine-agnostic files in `hermes/launchd/`:

- **`bin/hermes-gateway-multiplex`** — the launcher. Sets its own `PATH` (a
  LaunchAgent can start with a stripped one), `cd`s to `~/Workspaces`, logs to
  `~/.hermes/logs/gateway-multiplex.log`, `eval`s the `global` + `hermes`
  Keychain layers (minus messaging keys) into the process env for raw-env
  readers and subprocess inheritance — the scope-aware keys come per profile
  from `secrets.command` (see [`models-auth.md`](./models-auth.md) "Secrets
  layering") — re-syncs the Brave clone, then execs the checkout's
  `.hermes/bin/hermes gateway run --accept-hooks --external-supervisor` with
  `HERMES_SUPERVISED_CHILD=1` (no `-p` — default is the multiplex host; no
  `--replace` — a KeepAlive respawn must not re-arm takeover). The supervisor
  flags let `hermes update` drain the process and leave the respawn to launchd.
  Every path is `$HOME`-relative; no `.env`. (`secret env` has **no `-- <cmd>`
  form**, hence the `eval`.) It exports no `HERMES_PROFILE`: one process serves
  many profiles.
- **`ai.hermes.multiplex.plist.tmpl`** — LaunchAgent template with a
  `__HOME__` placeholder (launchd can't expand `~`). Runs the launcher as
  `ProgramArguments[0]`, so the login item reads `hermes-gateway-multiplex`, not
  `sh`. The `ai.hermes` label prefix gives Hermes its launchd identity (drain
  budget from `ExitTimeOut`, restart route), while not being `ai.hermes.gateway*`
  means `hermes gateway install/start/update` never regenerates it over the
  Keychain launcher. `KeepAlive` is `SuccessfulExit: false` (a clean exit parks
  the job; exit 75 and crashes relaunch), `ThrottleInterval` 30,
  `ExitTimeOut` 60.
- **`gateway-launchctl.sh`** — renders the template (`__HOME__` → `$HOME`) into
  `~/Library/LaunchAgents/` (host-local, never committed) and loads it; on
  install it also unloads the launcher's `LEGACY_LABELS` agents so two pollers
  never race one bot token.

**Telegram + Discord.** No synchronous SQLite in the gateway: gateway DB calls
run off the asyncio loop (`AsyncSessionDB` / `asyncio.to_thread`) because
synchronous access from `_handoff_watcher` stalls Discord heartbeats. Keep the
Discord toolset granular and equal to Telegram; never replace either list with
a broad bundled toolset.

Discord is limited to the private config's user and channel allowlists. A channel
mention creates a thread; the parent channel's `assistant-pipeline` binding and
prompt carry into that thread. Live voice uses `/voice join` and the existing
STT/TTS fallback chains. It leaves after five idle minutes by default, and a
gateway restart requires a manual rejoin. Cron/system Inbox delivery stays on
Telegram to avoid duplicate proactive notifications.

**Per-profile tool resolution.** In one multiplex process, toolset resolution
must be memoized per profile scope as well as per registry generation (upstream
behavior) — otherwise warming one profile's `tts` entry hides
scope-registered tools such as character-voice from another.
`test_audio_creator_routing.py` exercises the real resolver across scopes;
registration-only tests and direct CLI synthesis cannot detect this
gateway-specific failure.

Activate on the **gateway host only** (one bot token = one live connection;
stop any gateway elsewhere first):

```
hermes/launchd/gateway-launchctl.sh install      # render template + load
hermes/launchd/gateway-launchctl.sh status        # check
hermes/launchd/gateway-launchctl.sh uninstall      # unload + remove
```

## Tracking

Per-profile files in `hermes/profiles/<name>/`, symlinked by `install.sh`
(tracked unless noted): `config.yaml` (assistant: private, seeded from the
tracked `config.example.yaml`), `profile.yaml` (holds the routing `description`),
`SOUL.md` (untracked; seeded from the tracked `SOUL.example.md`), `skills/`,
`.no-bundled-skills` (`mcp.json` when present). `cron/`
is never linked or tracked — Hermes owns it machine-local. Everything outside
the symlink set stays untracked (inert `~/.hermes/kanban.db`, `kanban/`,
`workspace/`, `auth.json`, `.env`, `memories/`, `sessions/`, `state.db*`);
adoption steps are in [`ops/tracking.md`](ops/tracking.md) "Tracking a profile".

Routing quality depends on `profile.yaml` descriptions — create workers with
`hermes profile create <name> --description "<role>"` (or
`hermes profile describe <name> --text "…"`).
