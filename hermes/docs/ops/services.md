# Services and launchers

The LaunchAgents and engine/launcher scripts the Hermes setup runs: naming
rules, what each launcher manages and where its design lives. Read it before
adding, renaming or restarting a service, or when you need the command that
manages one.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Services and launchers

LaunchAgents are host-rendered from the templates in `launchd/`; the rendered
plists land in `~/Library/LaunchAgents/` and are never committed.

**Naming.** The gateway is `ai.hermes.multiplex` — it must start with
`ai.hermes` (Hermes reads its launchd identity from that prefix) and must not be
`ai.hermes.gateway*` (`hermes gateway install` would overwrite it). Every other
agent is `local.hermes.<plugin-or-engine>.<role>`, managed by the matching
`launchd/<plugin-or-engine>-launchctl.sh`, so it never looks like the gateway to
Hermes. Each plist's `ProgramArguments[0]` is a `launchd/bin/hermes-<name>`
launcher that only `exec "$@"`, so Login Items and Background Items show that
name instead of "Python".

### Gateway

`launchd/gateway-launchctl.sh {install,restart,status,uninstall}` manages the
multiplex gateway (`ai.hermes.multiplex`), **one host only** (one bot token = one
live connection). **Restart = `restart`** (or `/restart` in chat): SIGUSR1, the
gateway's planned restart — it lets running turns finish (up to
`agent.restart_after_turn_timeout`), drains the rest, marks interrupted turns to
resume, exits 75 and launchd relaunches it. The launcher waits that whole window
and never forces the stop (the budget: [operations.md](../operations.md)
"Gateway as a persistent service"). `install` re-renders the plist and takes the same
path when nothing changed; only a changed plist is reloaded, which SIGTERMs the
gateway as an unplanned stop. **Stop = `uninstall`**. **Never** run `hermes gateway run`
or `restart` in a terminal while it is loaded — a second poller causes Telegram
`getUpdates` 409 conflicts (`pgrep -fl 'gateway run'` ⇒ exactly 1). The A2A
endpoints are the loopback ports `9903`–`9909`, one per A2A-serving profile
(`platforms.a2a.extra.port` in each profile's config; the roster in
[topology.md](../topology.md) lists them). Design and plist
semantics: [docs/operations.md](../operations.md) "Gateway as a persistent
service"; rules: [`AGENTS.md`](../../AGENTS.md) "Gateway and A2A".

### Engines

**Runtime root.** Every engine's machine-local state — venvs, model weights,
cloned servers and browsers, voice catalogs and bundles, rendered settings —
lives under one root outside the repository: `HERMES_LOCAL`, by default
`~/.hermes/local/`, as `<root>/<engine>/`. The engine directory names
(`web3`, `twscrape`, `qwen3-tts`, …) are fixed: the access guards recognise
`local/<engine>` in a command. Every launcher, script, plugin and engine
resolves the root through that one contract, never from its own source
location, and every artifact an engine writes under its directory names
other files there relative to it (the Qwen catalog and its manifests, the
Stable Audio marker and weight links, the Motion Canvas and Three markers) —
so the root can move, and `HERMES_LOCAL` is the only thing that has to know
where it is. What the launchers render for launchd (plists, Irodori's `.env`,
SearXNG's settings) carries absolute paths by nature and is re-rendered by
`install`. A non-default root is one value for the whole machine: the
gateway's environment (the plugins read it once at load), every launcher
`install` and every maintainer command must see the same `HERMES_LOCAL`, and
its engine directories keep their names, which the access guards recognise
in either spelling (`local/<engine>`, `$HERMES_LOCAL/<engine>`).

- `launchd/qwen3-tts-launchctl.sh {install,register,unregister,voices,status,uninstall}`
  — Qwen3-TTS on `:10102`; see [tts-engines.md](tts-engines.md) "Qwen3-TTS voice
  catalog".
- `launchd/irodori-tts-launchctl.sh {install,register,register-lexicon,unregister,restart,voices,status,uninstall,purge}`
  — Irodori-TTS on `:10103`; see [tts-engines.md](tts-engines.md) "Irodori voice
  registration".
- `launchd/searxng-launchctl.sh {install,restart,status,uninstall}` — SearXNG
  metasearch on `127.0.0.1:10104` (`SEARXNG_PORT` overrides), the keyless floor
  of the web search cascade; see [web-search.md](web-search.md) "Floor". It runs
  the container pinned in `engines/searxng/image.lock` through Docker Desktop
  (`scripts/searxng-run.sh` in the foreground, so launchd owns its lifetime) and
  renders `engines/searxng/settings.yml.tmpl` into `~/.hermes/local/searxng/`
  with a host-generated cookie key. Hermes engine ports run `1010x`; pick the
  next free one for a new engine, never a common development port.

### Account sync agents

Each keeps a local mirror of the user's own account current for its plugin and
always targets the live checkout (some commands that change an agent or the
account also refuse a task worktree; each launcher says which).

- `launchd/discord-access-launchctl.sh {setup,install,uninstall,run,status}` —
  [docs/discord-access.md](../discord-access.md).
- `launchd/telegram-access-launchctl.sh {setup,login,logout,install,uninstall,restart,status}`
  — [docs/telegram-access.md](../telegram-access.md).
- `launchd/signal-access-launchctl.sh {link,setup,install,uninstall,restart,status}`
  — [docs/signal-access.md](../signal-access.md).
- `launchd/whatsapp-access-launchctl.sh {pair,install,uninstall,restart,status}`
  — one agent per named account; [docs/whatsapp-access.md](../whatsapp-access.md).

### Engine and access scripts

Not LaunchAgents: they build an engine (a hash-locked venv, or a helper app from
in-tree sources, under the machine-local `~/.hermes/local/`) and report state without printing
secrets.

- `scripts/x-access.sh {install,status}` — the x-access engine venv and the
  state of the sub-account's cookies; see [docs/x-access.md](../x-access.md).
- `scripts/substack-access.sh {install,status}` — the substack-access engine
  venv and the state of the account's cookies; see
  [docs/substack-access.md](../substack-access.md).
- `scripts/youtube-access.sh {install,status}` — the youtube-access yt-dlp venv,
  Deno/ffmpeg and the authorized channels; channels themselves are authorized
  with `yaccess auth`; see [docs/youtube-access.md](../youtube-access.md).
- `scripts/web3.sh {install,status,addresses,new-wallet}` — the web3 engine venv,
  stored wallet items and keys by name, and new Hermes wallets; see
  [docs/web3.md](../web3.md).
- `scripts/screen-listen.sh {identity,install,status,grant,grant-screen,grant-mic}` — the
  screen-listen helper app (built with the system Swift toolchain, not a venv,
  signed with a local identity so rebuilds keep their consents), which
  processes are playing audio, the one-time System Audio Recording consent,
  and the Screen Recording one for video; see
  [docs/screen-listen.md](../screen-listen.md).
- `scripts/brave-agent-sync.sh {sync,check,path,remove}` — the real-profile Brave
  clone ([browser.md](browser.md)). `sync` (default) re-clones when
  `/Applications/Brave Browser.app` changed version or the clone is missing,
  terminating a running clone first (the gateway launcher runs it before every
  start; run it by hand after a Brave update rather than wait); `check` exits 0
  when the clone matches; `path` prints the `real_profile_binary` value;
  `remove` deletes the clone and any running instance.

## Work continuity and candidates

`scripts/verify-work-continuity.py --runtime <hermes-agent-checkout> --private
<paired-private-checkout>` is the gate before a cutover and after an upstream
update; it installs, restarts and migrates nothing. What it proves and the
rollout order: [docs/topology.md](../topology.md) "Candidate rollout and
cutover"; the rules around it: [`AGENTS.md`](../../AGENTS.md) "Candidates and
cutover". To run public tests that read private config against a paired
candidate, set `HERMES_PRIVATE_ROOT=<private-checkout>` (absent = those tests
skip); it selects a source tree for tests, not runtime wiring.
