# Gateway, tracking and status

Gateway as a persistent service, what is tracked, and the as-built status. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Gateway as a persistent service

The **default** profile hosts ONE multiplex gateway (and the embedded kanban
dispatcher) keychain-pure via a **LaunchAgent**: `gateway.multiplex_profiles:
true` + the allowlist (assistant, engineer, creator, marketer, writer,
researcher) in the root `config.yaml` make that single process connect every
served profile's enabled platforms — assistant Telegram (+ topics) and
Discord, the engineer / creator / marketer Telegram bots, and the A2A
endpoints on 127.0.0.1:9902-9906. Secondary profiles never run their own
gateway. Three tracked, machine-agnostic files in `hermes/launchd/`:

- **`hermes-gateway-multiplex`** — the launcher. Sets `PATH`, `cd`s to
  `~/Workspaces`, logs to `~/.hermes/logs/gateway-multiplex.log`, `eval`s the
  `global` + `hermes` Keychain layers into the process env (raw-env readers +
  subprocess inheritance; the scope-aware keys come per profile from
  `secrets.command`), then execs the real `hermes gateway run` (no `-p` —
  default is the multiplex host). Every path is
  `$HOME`-relative — no
  hardcoded home, no `.env`. (`secret env` has **no `-- <cmd>` form**, hence the
  `eval`.) It exports no `HERMES_PROFILE`: one process serves many profiles.
- **`local.hermes.gateway.multiplex.plist.tmpl`** — LaunchAgent template with a
  `__HOME__` placeholder (launchd can't expand `~`). Runs the launcher as
  `ProgramArguments[0]`, so the login item reads `hermes-gateway-multiplex`, not
  `sh`.
- **`gateway-launchctl.sh`** — renders the template (`__HOME__` → `$HOME`) into
  `~/Library/LaunchAgents/` (host-local, never committed) and loads it; on
  install it also unloads the legacy `local.hermes.gateway.assistant` agent so
  two pollers never race one bot token.

**Telegram + Discord.** Upstream #40695 previously let `_handoff_watcher` block
the asyncio loop on synchronous SQLite access, stalling Discord heartbeats and
the dispatcher. The installed fork now wraps gateway DB calls in
`AsyncSessionDB` / `asyncio.to_thread` and carries dedicated regression tests, so
the launcher exposes both platform credentials. Keep the Discord toolset
granular and equal to Telegram; never replace either list with a broad bundled
toolset.

Discord is limited to the private config's user and channel allowlists. A channel
mention creates a thread; the parent channel's `assistant-pipeline` binding and
prompt carry into that thread. Live voice uses `/voice join` and the existing
STT/TTS fallback chains. It leaves after five idle minutes by default, and a
gateway restart requires a manual rejoin. Cron/system Inbox delivery stays on
Telegram to avoid duplicate proactive notifications.

Activate on the **gateway host only** (one bot token = one live connection —
four bots means four tokens, all owned by this one process; stop
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
  / `.no-bundled-skills` per profile (`mcp.json` when present).
- `cron/` is never linked or tracked — Hermes owns it machine-local.
- Auto-untracked (outside the symlink set): `~/.hermes/kanban.db`, `kanban/`,
  `workspace/`, `auth.json`, `.env`, `memories/`, `sessions/`, `state.db*`.

Routing quality depends on `profile.yaml` descriptions — create workers with
`hermes profile create <name> --description "<role>"` (or
`hermes profile describe <name> --text "…"`).

## Status (as-built)

Built and verified through v4 (2026-07 → 2026-08-03): the six specialists,
the assistant gateway (keychain-pure LaunchAgent; Telegram + Discord after
upstream issue #40695's async-DB fix; `dispatch_interval_seconds: 15`), model
chains (doctor + live probes), and
the v4 contract's Phase 7 verification (89 tests, live canaries, subscribed
QA). Active model slugs confirmed 2026-07: `anthropic` / `claude-opus-5`,
`xai-oauth` / `grok-4.3` (searcher T1), `openai-codex` / `gpt-5.6-sol`
(researcher T1 + fallbacks), OpenRouter tails `xiaomi/mimo-v2.5` (vision),
`minimax/minimax-m3` (image+video), `deepseek/deepseek-v4-flash`
(text-only).

**Workflow v5 rebuild (2026-08-06)** — driven by the 45s-PV postmortem (38
cards / 9 hours, over half spent on registration accidents, packaging
repair, and QA admission protocol): the v4 shape system, double approval,
fan-out manifests, digest/probe admission, QA cards, and the planner/qa
profiles were retired. Heavy work now runs in resident specialist sessions
(`resident-session.sh`: per-key serialization, session-id recapture,
close-on-acceptance; smoke-tested against creator with retained context);
the assistant owns planning (one conversational approval), the quality gate
(contracts then under `assistant-pipeline/references/quality-assurance/`), and GitHub bookkeeping;
the board shrank to fire-and-forget / cron / mass-parallel / `scheduled`
with a lean card contract. The completion path-guard plugin, admission
probes, and the 5-minute orphan watchdog were removed (the sweeper and the
guarded block resolver remain); the validator now enforces the
assistant-pipeline topology, routing completeness, `card_units` schema and
required QA contracts. Remaining live verification: a real short-video production run
through the new flow.

**Multi-primary peer rebuild (2026-09-01)** — assistant, engineer, creator,
and marketer were promoted to primaries: each runs its own Telegram bot out
of ONE default-hosted multiplex gateway (`gateway.multiplex_profiles`), and
the peer graph rides the A2A platform (per-profile `a2a_agents`, localhost
ports 9902-9906, `timeout: 310` because the caller default of 120s undercuts
the server's 300s reply window). writer / researcher became receive-only A2A
endpoints; researcher's `claim-verification` card was retired (research is
card-free; the assistant reaches research only through engineer / creator /
marketer). Secrets moved to per-profile scopes via `secrets.command` →
`scripts/profile-secrets.sh` (multiplex scope-aware reads never fall back to
the process env). Peer-list enforcement is config + operating contract
(`a2a_agents` names the callable peers; contracts forbid direct URLs), not a
plugin hook. The old v5 supervision shape (assistant as front door / quality
gate / dispatcher host, heavy work in resident sessions) is retained for
now, with a stated intent to move stepwise toward a flatter, equal-primary
operation. Verified live 2026-09-01/02: 4 bots + Discord connected, A2A
round-trips (assistant→writer, engineer→researcher), dispatcher singleton,
cron ticking all 7 profiles. First regression found and fixed 2026-09-02:
upstream's completion-notification injector only knew `self.adapters`, so a
resident-session turn finishing in the assistant's (now secondary) chat
never woke it — carried fix `fix/watch-notification-multiplex-route` in the
hermes-agent checkout (see AGENTS.md).

**Creator hands v3 (2026-09-05, in progress)** — see [`hands/overview.md`](./hands/overview.md) "Creator hands (v3)".
Started after the `refactor/creator-profile` branch (director + three hands +
menu / preset / Style governance) was abandoned as over-abstracted. Progress
is tracked per family in that section's "Migration" list; the first family
is `icon` on `image-creator`, the second `emoji`.
