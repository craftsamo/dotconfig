# Hermes Agent

Mechanics of the `hermes/` subtree: install, symlinks, layout, tracking, secrets,
engines, browser/web-search/voice plumbing and commands. Behavior contracts of
the agents live in [`docs/`](./docs/) (index: [`PROFILES.md`](./PROFILES.md));
maintainer rules live in [`AGENTS.md`](./AGENTS.md).

Hermes is the self-improving agent CLI by Nous Research. It keeps everything
under `~/.hermes/` and does **not** read `~/.config`, so
[`install.sh`](../install.sh) symlinks the version-controlled files into place.

**Contents:** [Where behavior lives](#where-behavior-lives) ·
[Installing the binary](#installing-the-binary) · [Symlinks](#symlinks) ·
[Layout](#layout) · [Tracked vs ignored](#tracked-vs-ignored) ·
[Profiles](#profiles) ([Tracking a profile](#tracking-a-profile)) ·
[Skills](#skills) · [Cron](#cron) · [Plugins](#plugins) · [Secrets](#secrets) ·
[Web dashboard (tailnet)](#web-dashboard-tailnet) ·
[Capabilities & dependencies](#capabilities--dependencies) ·
[Local TTS engines](#local-tts-engines) ·
[Speech-to-text](#speech-to-text--fallback-chain) ·
[Audio hands tooling](#audio-hands-tooling) ·
[Web search backends](#web-search-backends) · [Browser](#browser) ·
[Worker terminal approvals](#worker-terminal-approvals) · [Commands](#commands)

## Where behavior lives

This file does not restate agent behavior. Contracts:

| Topic | Contract |
| --- | --- |
| Engineer modes, OpenCode runtime, resident turns, UI evaluators | [docs/profiles/engineer.md](docs/profiles/engineer.md) |
| `specialist_call` / `specialist_session`, completion, deadlines, work continuity | [docs/profiles/specialist-calls.md](docs/profiles/specialist-calls.md) |
| Assistant entry routing, creative early delivery, kanban catalog, pinned topics | [docs/profiles/assistant.md](docs/profiles/assistant.md) |
| Writer v8 leaves, Marketer v8 entries, Researcher/Searcher phases | [writer.md](docs/profiles/writer.md), [marketer.md](docs/profiles/marketer.md), [research.md](docs/profiles/research.md) |
| Entry loading contract, candidate rollout and cutover | [docs/topology.md](docs/topology.md) |
| Creator v9 broker phases | [docs/broker.md](docs/broker.md) |
| Hands entry routing and instruction context | [docs/hands/overview.md](docs/hands/overview.md) "Skill tree" |
| Character voices, performance direction, Speech / SFX / Music / Mix families | [docs/hands/audio.md](docs/hands/audio.md) |
| Model chains, auth inheritance, what belongs in each secret layer | [docs/models-auth.md](docs/models-auth.md) |
| Gateway service design | [docs/operations.md](docs/operations.md) "Gateway as a persistent service" |

## Installing the binary

Outside the [Brewfile](../Brewfile). Run [`./setup.sh`](./setup.sh) — an
idempotent installer that clones the agent via `ghq`, builds a Python 3.11 venv
with `uv` (installing the `EXTRAS` capability set — `all,voice,messaging,
tts-premium` — plus `faster-whisper` for free local STT), and symlinks
`~/.local/bin/hermes` (already on `PATH` behind the shim). It makes no shell-rc
edits and runs no interactive wizard. Trim `EXTRAS` / `EXTRA_PIP` at the top of
`setup.sh` for a leaner venv.

```sh
~/.config/hermes/setup.sh     # install (safe to re-run)
hermes --version              # verify
```

Requires `ghq` + `uv` (both from `./install.sh --deps`). To update later, use
`hermes update` (git pull + re-sync), not this script. The upstream
`setup-hermes.sh` is deliberately avoided: it appends a PATH line to `~/.zshrc`,
which is a symlink into this repo.

`setup.sh` installs only the binary. Run [`../install.sh`](../install.sh)
separately for the `~/.hermes/` symlinks, and store keys with `secret set …`
(no `.env`).

## Symlinks

Every link below points back into this repo, so edit the repo copy.
`install.sh`'s `link()` never overwrites a real file — it prints
`WARN … not overwriting` and skips (the repo-wide drift policy).

| Symlink | Target |
| --- | --- |
| `~/.hermes/config.yaml` | `hermes/config.yaml` |
| `~/.hermes/SOUL.md` | `hermes/SOUL.md` (untracked; see below) |
| `~/.hermes/mcp.json` | `hermes/mcp.json` |
| `~/.hermes/skills` | `hermes/skills/` |
| `~/.hermes/plugins` | `hermes/plugins/` |
| `~/.hermes/.no-bundled-skills` | `hermes/.no-bundled-skills` |

For every `hermes/profiles/<name>/`, `install.sh` links into
`~/.hermes/profiles/<name>/`: `config.yaml`, `profile.yaml`, `SOUL.md`,
`mcp.json`, `scripts/`, `skills/` and `.no-bundled-skills` when present, plus
the shared `hermes/plugins/` (plugin discovery is `HERMES_HOME`-scoped). It
never links `cron/` and migrates an old cron link back to a real directory.

`install.sh` seeds a missing `SOUL.md` from the tracked `SOUL.example.md` and the
assistant's missing `config.yaml` from `config.example.yaml`; seeded copies stay
untracked. The private overlay (`~/.config/private`, the `private-dotconfig`
repo), when present, runs its own `install.sh` last and overlays the real
`SOUL.md` files and `profiles/assistant/config.yaml` into this tree.

## Layout

```
config.yaml            # default profile: model/providers, toolsets (Hermes-rewritten)
SOUL.example.md        # persona template; real SOUL.md is private/untracked
mcp.json               # MCP servers ({} = none)
.no-bundled-skills     # bundled-skill seeding opt-out marker
                       # (no cron/ — Hermes owns ~/.hermes/cron, machine-local)
skills/
  default-pipeline/    # thin CLI adapter for default over the assistant's
                       #   assistant-pipeline kernel/entry tree
  learned/             # runtime-authored skills; mutable, ignored
plugins/               # backend chains, tool overrides, specialist/OpenCode
                       #   transports, Worker guards; source tracked
launchd/               # multiplex gateway launcher + plist template, local
                       #   TTS engine launchers + plist templates
engines/               # tracked pins/locks: irodori-tts, qwen3-tts,
                       #   stable-audio-3, motion-canvas, three-webgl
scripts/               # profile-secrets.sh (secrets.command helper),
                       #   brave-agent-sync.sh, validate-profile-skills.py,
                       #   check-local-patches.sh,
                       #   verify-work-continuity.py, audit-hands-references.py,
                       #   qwen3_tts_server.py, qwen3_tts_reading_check.py,
                       #   stable_audio3.py, tests/ (pytest suites + fixtures)
local/                 # ignored machine-local installs: engine venvs/weights,
                       #   brave-agent clone bundle, …
docs/                  # behavior/design contracts (index: PROFILES.md)
profiles/<name>/       # bots: assistant, engineer, creator, marketer; specialists:
                       #   writer, researcher, searcher; Creator's hands:
                       #   image-, video-, audio-creator; resident-only UI
                       #   evaluators: ui-review, ux-persona
  config.yaml          # model/fallback + agent.system_prompt (operating contract);
                       #   assistant tracks config.example.yaml instead
  profile.yaml         # routing description (kanban/delegation)
  SOUL.example.md      # persona template; real SOUL.md (BASE + role posture) untracked
  .no-bundled-skills
  skills/              # <profile>-pipeline/ (the one root pipeline skill;
                       #   assistant's is a private-overlay symlink), technic/
                       #   (flat leaf technics, where used), learned/ (ignored)
  scripts/             # assistant: resident-session.sh, kanban-resolve-block.sh,
                       #   kanban-scheduled-sweeper.sh, creative-timeline.py,
                       #   local-* cron wrappers (generated, ignored);
                       #   creator: hyperframes-env.sh
  external-skills/     # writer: curated japanese-writing symlink
setup.sh README.md PROFILES.md AGENTS.md
```

Shared `skills/` holds only `default-pipeline/` and `learned/`; creative skills
live under `profiles/creator/skills`. Skill placement (validator-enforced):

- Every worker has exactly ONE root pipeline skill `<profile>-pipeline`
  (lifecycle + capability router, auto-loaded by its operating contract); entry
  and leaf shapes per profile are in the per-profile docs.
- Directly selectable leaf technics sit exactly one directory below
  `skills/technic/` (flat canonical leaves) and are pinned per card via
  `kanban_create skills:[...]`. A technic's references are modes only when
  tools, spend class and QA stay the same; styles/presets/formats remain
  references. Creator's `creator-*` technics stay 1:1 with the assistant's
  legacy Plan leaves ([docs/broker.md](docs/broker.md)).
- Researcher/Searcher entries own plain `references/<unit>.md` (4/3); Researcher
  shares parent `references/gather.md`; Searcher has no technics.
- Writer reads the `japanese-writing` core through its curated
  `external-skills/` symlink; Marketer reads Writer's pipeline as an external
  reference for shared caller QA.
- The assistant's `assistant-pipeline` (kernel + 19 child entries + shared mode
  references) is a private-overlay symlink; its pinned Telegram topics bind no
  skill (their contracts are `channel_prompts` entries).
- `learned/` is never a dispatch or Git ownership surface.

## Tracked vs ignored

**Tracked:** root `config.yaml` / `mcp.json` / `.no-bundled-skills`; per profile
`config.yaml` (assistant: `config.example.yaml`), `profile.yaml`,
`.no-bundled-skills`, `skills/<profile>-pipeline/` and `skills/technic/`,
`scripts/`; every `SOUL.example.md`; `skills/default-pipeline/`; `plugins/`
source; `launchd/`; `engines/`; `scripts/`; docs.

**Ignored** (see [`../.gitignore`](../.gitignore)): every `SOUL.md` and
`profiles/assistant/config.yaml` (private overlay); `auth.json`, `.env*`,
`memories/`, `sessions/`, `state.db*`, `logs/`, `workspace/`, `plans/`,
`*_cache/`, `local/`, `browser-profile/` (copied cookies — must never ship);
`specialist-sessions/`, `resident-sessions/`, `opencode-sessions/`; skill
bookkeeping (`.bundled_manifest`, `.usage.json*`, `.curator_*`, `.archive/`,
`.hub/`, `index-cache/`, `.restore-backups/`); every other directory under
`skills/` (`learned/`, seeded categories); `profiles/*/scripts/local-*.sh`;
Marketer lease files; `**/__pycache__/`, `*.pyc`; the
`plugins/hermes-achievements/` runtime data. `cron/` is absent entirely — it is
not linked, so nothing it writes reaches the repo. Never commit secrets, state
or host-rendered plists (`~/Library/LaunchAgents/…`).

**Skill ownership follows the directory type.** Shared `default-pipeline/` and
every worker's `<profile>-pipeline/` and `technic/` are maintainer-owned and
tracked normally. The assistant's `assistant-pipeline/` is maintainer-owned too
but lives in the private overlay — a symlink into `~/.config/private`, because
it encodes the personal messaging operation and this repo is public. Edit it
through the same path; commit in the overlay repo. Never use `skip-worktree` for
managed skills: their changes must remain visible in `git status`.

**Promoting a learned skill** is an explicit review step: review it, move the
complete package from `learned/` into `technic/`, set
`metadata.hermes.category: technic` and normalize its routing, add it to the
pipeline's capability registry when applicable, pin an agent-created source
against curator writes with `hermes -p <profile> curator pin <name>`, then
commit it normally.

## Profiles

Named profiles live under `~/.hermes/profiles/<name>/` — each its own
`HERMES_HOME` with its own `config.yaml` / `SOUL.md` / `skills/` / `cron/` /
state. The alias `~/.local/bin/<name>` is a wrapper that runs
`exec hermes -p <name> "$@"` — **bare `hermes`**, so it still resolves through
the `bin/hermes` shim and the shared `global` + `hermes` Keychain layers are
injected for every profile. The default profile is `~/.hermes` itself. Roster
and roles: [docs/topology.md](docs/topology.md) "Profile roster".

### Tracking a profile

Because `hermes profile create` writes **real** files into
`~/.hermes/profiles/<name>/` and `link()` never replaces a real file, move them
into the repo (clearing the real files) before linking:

1. `hermes profile create <name> --description "<role>"` — seeds state + the
   `~/.local/bin/<name>` alias. Routing quality depends on the description
   (`hermes profile describe <name> --text "…"` to change it).
2. Stop bundled-skill seeding so bundled skills stay in `external_dirs`:
   ```sh
   hermes -p <name> skills opt-out --remove --yes
   ```
3. Move the version-controllable files into the repo (skip any that don't exist):
   ```sh
   mkdir -p ~/.config/hermes/profiles/<name>
   mv ~/.hermes/profiles/<name>/{config.yaml,profile.yaml,SOUL.md,mcp.json,skills} \
      ~/.config/hermes/profiles/<name>/
   ```
   Commit a `SOUL.example.md` persona template; `SOUL.md` itself stays
   untracked (put the real one in the private overlay). A config holding private
   identifiers follows the assistant pattern: track `config.example.yaml`, keep
   the real `config.yaml` in the overlay.
4. In that profile's `config.yaml`, point `skills.external_dirs` at the clone
   (`~/ghq/github.com/NousResearch/hermes-agent/skills`) — same as default.
5. `./install.sh` — the `[hermes]` loop now symlinks them (no WARN).

State (`memories/`, `sessions/`, `state.db*`, `cron/`, …) stays in
`~/.hermes/profiles/<name>/` — never moved, never tracked. A new bot also needs
a `hermes-<name>` Keychain layer and a multiplex allowlist entry — see
[docs/topology.md](docs/topology.md) "Multiplex gateway and A2A peer graph".

### Caveats

- **Order matters / "already installed".** The symlink must exist *before*
  Hermes writes a real file. If real files already exist (a named profile, or a
  `~/.hermes/` set up before this repo), `install.sh` won't replace them — use
  the move-then-`install.sh` adoption above. Hermes itself runs fine either way;
  only the symlink tracking is affected.
- **Background / launchd processes** may start with a restricted `PATH`. The
  multiplex gateway launcher sets `PATH` explicitly and injects the approved
  Keychain layers before `exec`; other services must follow the same pattern.

## Skills

`~/.hermes/skills` and each profile's `skills/` are symlinks into this repo.

- **Runtime creates land in `learned/`.** Every `config.yaml` sets
  `skills.create_dir: skills/learned` (`HERMES_HOME`-relative,
  validator-enforced), which `skill_manage` consults on every create —
  background review, curator, `/learn`, the `/skills approve` replay, flat or
  `operations[]` call shape — so new skills land at
  `HERMES_HOME/skills/learned/[<category>/]<name>`. The `skill-topology` plugin
  does not do this placement (its old rewrite missed batched `operations[]`
  creates); it no longer rewrites skill creation.
- **Bundled skills stay out of the repo.** Seeding is disabled:
  `hermes skills opt-out --remove` writes a `.no-bundled-skills` marker, tracked
  here and linked by `install.sh` so the opt-out reproduces on a fresh machine.
  `skills.external_dirs` points at the agent clone
  (`~/ghq/github.com/NousResearch/hermes-agent/skills`), so bundled skills are
  read in place (read-only, refreshed by `hermes update`).
- **Upstream wiring is `external_dirs`-only.** Official `skills/` libraries
  attach per category directory, `optional-skills/` per individual skill
  directory, pruned via `skills.disabled` (see each profile's `config.yaml`).
  Never run `hermes skills install` — it copies into `~/.hermes/skills`, i.e.
  this repo. The setup-gated candidate backlog is the "Upstream wiring pattern"
  paragraph in [docs/topology.md](docs/topology.md).
- **Upstream still seeds past the opt-out.** Each gateway launch writes
  `autonomous-ai-agents/DESCRIPTION.md` into the running profile's skill root,
  and an upgrade that changes a bundled skill copies the whole skill in. A lone
  `DESCRIPTION.md` is harmless (ignored, no `SKILL.md`; deleting it only invites
  it back). A seeded `SKILL.md` fails `validate-profile-skills.py` with
  `unexpected skill root`. So **after every `hermes update`**, run the validator
  and delete any category directory under `profiles/*/skills/` that is not
  `<profile>-pipeline`, `technic` or `learned`; the skills stay readable via
  `skills.external_dirs`.
- **Private and shared stores.** The `~/Workspaces` data-skill cluster lives in
  the private overlay and is read through `skills.external_dirs` as
  `~/.config/private/hermes/skills`. HyperFrames / `media-use` playbooks and the
  curated `media-craft-*` skills are read from `~/.agents/skills` via
  `external_dirs`; the store's maintenance rules are in `AGENTS.md`. A fresh
  machine needs `hyperframes skills update` before creator can load them.

## Cron

`~/.hermes/cron` (and each profile's) is a real machine-local directory this
repo neither links nor tracks. Hermes `mkdir -p`s it and owns every file in it:
`jobs.json`, `output/`, `executions.db`, `.tick.lock`, `.jobs.lock`,
`ticker_*`, `catch_up_occurrences`, `suggestions.json`. Definition and run-state
share one file, so tracking `jobs.json` meant constant churn.

- Do **not** re-link it, and do **not** re-add it with `skip-worktree` — that
  flag hid new jobs from `git status` and made branch switches fail on a
  dirty-but-invisible file.
- A missing `jobs.json` is read as **zero jobs, silently**, and nothing
  recreates it — back it up before touching that directory.
- The private `local-*` schedules are re-creatable from the `hermes cron create`
  commands in the private overlay's README. Hermes' scheduler only runs a script
  resolving inside `<HERMES_HOME>/scripts`, so the overlay's `install.sh`
  generates the ignored `profiles/*/scripts/local-*.sh` wrappers.

## Plugins

`~/.hermes/plugins` (and each profile's) is symlinked to `hermes/plugins/`, so a
new plugin needs no re-`install.sh` — only `plugins.enabled` (and any toolset)
in the relevant `config.yaml`. After a plugin enablement change the multiplex
gateway needs one normal drained restart (`/restart` or
`gateway-launchctl.sh install`); never launch a second gateway.

**Media stack.** Backends are chosen via `*_gen.provider` / `tts.provider` /
`stt.provider` plus `*.fallback.chain`. These custom keys (and top-level ones
such as `video_analyze:`) survive Hermes' config rewrites because `_deep_merge`
keeps user keys.

- **image_gen/image-fallback** (`backend`): `img-codex-xai`, `img-xai-codex-fal`,
  `img-codex-xai-fal` (Creator's chain) — names spell the order. Capabilities:
  [docs/hands/image.md](docs/hands/image.md) "Image generation capabilities".
- **video_gen/video-fallback** (`backend`): `vid-xai-fal` (Grok Imagine → FAL),
  `vid-fal-xai`.
- **video-analyze-mimo** (`standalone`): overrides `video_analyze` with a fixed,
  config-driven backend (`video_analyze: {provider, model}`, default OpenRouter /
  `xiaomi/mimo-v2.5`), so `auxiliary.vision` can stay `auto` and images route
  natively to the main model. **Pinning `auxiliary.vision` to a video-capable
  model disables the main model's native image vision.**
- **tts/tts-fallback** (`backend`, `tts.provider: tts-fallback`) and
  **tts/irodori-tts** / **tts/qwen3-tts** (`backend`, loopback clients): see
  [Local TTS engines](#local-tts-engines).
- **tts/character-voice** (`standalone`): AudioCreator-only character tools; it
  owns no backend and resolves an engine from the TTS registry directly.
  Contract: [docs/hands/audio.md](docs/hands/audio.md) "Character voices and
  performance direction".
- **transcription/stt-fallback** (`backend`): see
  [Speech-to-text](#speech-to-text--fallback-chain).
- **audio_gen/sfx-gen**, **audio_gen/music-gen** (`standalone`): audio-creator
  only, with the dedicated `sfx_gen` / `music_gen` toolsets.

**Transports and guards.**

- **specialist-call** (`standalone`): the `specialist` toolset for assistant,
  creator, marketer and engineer. Enable `specialist-call` in `plugins.enabled`,
  `specialist` in the relevant `platform_toolsets` lists, and configure the
  explicit `specialist_call.resident_targets` allowlist. Behavior:
  [docs/profiles/specialist-calls.md](docs/profiles/specialist-calls.md).
- **opencode** (`standalone`): `opencode_call` / `opencode_session` for engineer
  and assistant. Enable the plugin and `opencode` toolset plus
  `opencode_cli.enabled: true`; optional `opencode_cli.models` sets per-agent
  overrides, otherwise OpenCode's defaults apply. The CLI resolves through
  `PATH`, preserving the secret shim. Behavior:
  [docs/profiles/engineer.md](docs/profiles/engineer.md) "OpenCode runtime".
- **ui-inspection** (`standalone`): `ui_capture` for ui-review / ux-persona.
- **writing-inspection** (`standalone`): Writer's bounded `writing_inspect`.
- **kanban-worker-mutation-guard** (`standalone`): stops dispatcher workers
  from creating, linking or releasing Kanban cards outside the Assistant path.
- **skill-topology** (`standalone`): the topology guard's home; it does not
  intercept dashboard direct-create APIs or arbitrary terminal/file writes — the
  validator catches those after the fact.
- `hermes-achievements/` holds only per-machine runtime data and is ignored.

## Secrets

No `.env` files. API keys live in the macOS Keychain and are injected at launch
by the [`bin/hermes`](../bin/secret-shim) secret-shim (`secret env -p global`
then `secret env -p hermes`). The `hermes` layer holds keys only Hermes uses
(e.g. `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `FAL_KEY`, `GROQ_API_KEY`, the
dashboard auth pair); it is injected for every `hermes` invocation, including
every profile alias. The `global` layer is for keys shared with other shimmed
tools (e.g. the web-search keys). Per-bot layers `hermes-assistant` /
`hermes-engineer` / `hermes-creator` / `hermes-marketer` hold each bot's
`TELEGRAM_BOT_TOKEN` (+ allowlists; assistant also carries the Discord keys).

The shim does not isolate profiles: every alias gets the same `global` +
`hermes` layers. Isolation happens in the multiplex gateway: each served
profile's `secrets.command` runs `scripts/profile-secrets.sh <profile>`, which
emits `global` + `hermes` + `hermes-<profile>` (the `hermes` messaging keys
filtered per profile), because
multiplex secret scopes never read the process env. Every config sets
`helper_timeout_seconds: 60`. Layer contents and the helper's one-shot design:
[docs/models-auth.md](docs/models-auth.md) "Secrets layering". CLI:
[`secret`](../zsh/functions/secret.md).

Rotating an API key needs a gateway restart: resident sessions inherit the
environment injected at gateway launch.

## Web dashboard (tailnet)

`hermes dashboard` runs a full web UI (config, API keys, sessions, and a Chat
terminal). tmux `prefix H` lazily starts one shared, machine-level dashboard in
a detached `hermes-dashboard` session that survives closing every directory's
TUI, so mobile devices on the tailnet can reach it anytime. See
[`tmux/README.md`](../tmux/README.md#hermes-web-dashboard) for the binding and
launch mechanics.

The dashboard binds to this machine's **Tailscale IPv4 only** (port `9119`) —
never `0.0.0.0` or the LAN — and Hermes' auth gate requires a login on every
non-loopback bind. It uses the bundled Basic provider:

- `dashboard.basic_auth.username` in `config.yaml` — the non-secret username.
- `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` / `HERMES_DASHBOARD_BASIC_AUTH_SECRET`
  — in the `hermes` Keychain layer, injected by `bin/hermes` at launch. The
  stable `SECRET` keeps sessions signed-in across restarts.

Provision both Keychain values once on a new machine. The password prompt does
not echo, and the signing secret goes directly from `openssl` to the Keychain:

```sh
secret set HERMES_DASHBOARD_BASIC_AUTH_PASSWORD -p hermes
openssl rand -base64 32 | \
  secret set HERMES_DASHBOARD_BASIC_AUTH_SECRET -p hermes --stdin
```

Browse `http://<tailnet-ip>:9119` from any tailnet device and sign in once. The
dashboard's web Chat starts its own profile-scoped TUI process — a parallel
entry point that shares the profile and saved sessions, not a mirror of an
in-progress terminal conversation.

## Capabilities & dependencies

**System packages** (declared in the [Brewfile](../Brewfile)): `ffmpeg` (TTS /
voice audio conversion), `portaudio` (CLI voice mode mic + playback), `opus`
(Discord voice-channel codec).

**`cua-driver`** (the macOS `computer_use` toolset — background desktop control)
has no Brewfile formula and needs one-time GUI grants:

```sh
hermes computer-use install      # fetches trycua/cua -> ~/.local/bin/cua-driver
cua-driver permissions grant     # grant Accessibility + Screen Recording
hermes computer-use status       # verify
```

`hermes update` refreshes the driver automatically when it's on `PATH`.

**API keys** — stored in the Keychain; the shim injects them. Run these
yourself (the value is read from a no-echo prompt, never argv):

```sh
secret set OPENROUTER_API_KEY -p hermes   # OpenRouter tiers + moa + vision + video analysis (mimo)
secret set GITHUB_TOKEN       -p hermes   # Skills Hub
secret set GROQ_API_KEY       -p hermes   # cloud STT (local faster-whisper needs no key)
secret set EXA_API_KEY        -p global   # web search (see Web search backends)
secret set PARALLEL_API_KEY   -p global
secret set FIRECRAWL_API_KEY  -p global
```

Other optional keys: `FAL_KEY` (image/video generation fallback, paid SFX/music;
resolved through the scoped Keychain helper — no new key, `.env`, provider-key
terminal passthrough or ElevenLabs subscription setup is needed for SFX),
`ELEVENLABS_API_KEY` (premium TTS / Scribe STT), `XAI_API_KEY` (x_search /
video_gen), `BROWSERBASE_API_KEY` (cloud browser). Bot tokens go in the per-bot
layers (see [Secrets](#secrets)).

## Local TTS engines

Two loopback-only engines run as LaunchAgents and take no API key:
`irodori-tts` on `127.0.0.1:10103` and `qwen3-tts` on `127.0.0.1:10102`.

**Language routing is the chain order, not a router.** `tts.fallback.chain` is
`irodori-tts → qwen3-tts → edge`. Irodori is Japanese-only — it mangles
English — so it *declines* English-dominant text (under 20% kana/kanji) by
raising, and the chain advances to Qwen3. No routing layer exists and none
should be added. The hand-off is per utterance on purpose: the same reference
voice sounds audibly different on the two engines, so splicing them inside one
sentence is audible. When a server is unavailable or still loading,
`tts-fallback` advances to the next tier and finally to Edge TTS
(`tts.edge.voice: ja-JP-NanamiNeural`); the call only errors if every tier
fails. Normal speech omits a voice ID and uses each engine's default. For a
pinned, named voice (no routing, no substitution), see
[docs/hands/audio.md](docs/hands/audio.md) "Character voices and performance
direction".

Auto-speech (`voice.auto_tts: true`, set for `default` + `assistant`) is
voice-in → voice-out in the gateway and TTS-on-by-default inside CLI voice
mode — it never auto-speaks plain text turns. After changing a live config,
restart the relevant Hermes process (e.g. the gateway).

**Voice data never enters this repo.** Reference audio lives in the private
character tree and is copied into the ignored `local/<engine>/` by the
launchers; the Irodori pronunciation lexicon is a private-overlay symlink
(`private/hermes/local/irodori-tts/lexicon.json`). Do not add a local-engine
voice (`voice:`) key under `tts.*` and do not name a lexicon or manifest path in
`config.yaml` — both are tracked.

**Irodori** runs fp32 on MPS (bf16 is CUDA/XPU-only upstream) from a git
checkout pinned in `engines/irodori-tts/pinned.conf`. It rewrites Latin proper
nouns to katakana through the private lexicon, then repairs its own WAV before
delivery: the in-pause codec rustle is gated, leading dead air and trailing
hallucinated fragments are trimmed, the onset click is faded and the level is
normalised. That repair uses numpy and the stdlib only, because the Hermes venv
carries no soundfile or scipy.

### Qwen3-TTS voice catalog

The `tts/qwen3-tts` plugin sends JSON speech requests to its loopback server;
the plugin applies `tts.speed` and output encoding with `ffmpeg`, then the
gateway handles its normal Opus delivery.

The server keeps one catalog-selected Base model resident on Apple MPS with BF16
and shares it across all registered voices. Voice-clone prompts are built lazily
and retained in a bounded LRU cache. FP16 is intentionally not used: the Base ICL
path can overflow in its code predictor on MPS. Every registered manifest must
pin the same model and exact Hugging Face commit; the server loads that local
snapshot so processor/tokenizer lookups cannot drift to `main`.

Voice-specific settings live in private character manifests, not in this public
repo. A manifest location (`/absolute/path/to/voice.json`) is supplied only
during machine-local registration. Each manifest contains the voice id,
language, model revision, generation seed, and paths to the approved reference
audio/transcript; it pins both reference SHA-256 digests and the PCM WAV
metadata. Reference paths are relative to the manifest, so the character tree
can move as one unit. The reference transcript and audio drive in-context
cloning, which carries the reference's prosody into synthesis — an expressive,
natural reference is the primary lever for output intonation.

A manifest may add an optional `pronunciation.lexicon` entry (`path` +
`sha256`) pointing to a JSON object of surface-form → reading substitutions.
The server applies the lexicon (longest surface first) after whitespace
normalization and before synthesis; use it to pin down words the model
misreads, not to rewrite whole sentences into kana. Long inputs are split into
sentence-aligned chunks (~200 chars, clause fallback), each chunk is generated
with the manifest seed re-applied, and the chunks are joined with a 150 ms
gap — this stabilizes intonation and avoids Japanese end-of-text truncation.

The first install registers the default voice. Additional characters are
registered by manifest without adding ports, providers, or LaunchAgents:

```sh
hermes/launchd/qwen3-tts-launchctl.sh install \
  --voice-manifest /absolute/path/to/voice.json
hermes/launchd/qwen3-tts-launchctl.sh register \
  --voice-manifest /absolute/path/to/another-voice.json [--default]
hermes/launchd/qwen3-tts-launchctl.sh unregister --voice another-voice
hermes/launchd/qwen3-tts-launchctl.sh voices
hermes/launchd/qwen3-tts-launchctl.sh install  # reuses the local catalog
hermes/launchd/qwen3-tts-launchctl.sh status
hermes/launchd/qwen3-tts-launchctl.sh uninstall
```

Validate a new manifest standalone before registering:
`python3 hermes/scripts/qwen3_tts_server.py check-manifest /path/to/voice.json`.
To find misreadings, run `hermes/scripts/qwen3_tts_reading_check.py --text "…"`
(or `--file corpus.txt`) against the live server: it synthesizes, transcribes
with faster-whisper, compares readings in kana and prints paste-ready lexicon
candidates. Findings are candidates, not verdicts — confirm by ear
(`--keep-audio DIR` keeps the wavs) before adding a lexicon entry and re-running
`install`. It resolves its own dependencies through `uv run`; the server venv
stays untouched.

`install` creates an isolated Python 3.12.11 venv under the ignored
`hermes/local/qwen3-tts/`, stores absolute private manifest locations only in the
ignored `catalog.json`, synchronizes the hash-locked
`engines/qwen3-tts/requirements.lock`, validates every manifest, renders the
LaunchAgent, and atomically activates the catalog. A failed registration,
service load, or identity-bound health check restores the previous catalog and
service. The tracked plist contains only the stable ignored catalog path. An
existing single-voice `voice.json` registration is migrated automatically on the
first catalog install. Model weights are cached below the same ignored
directory; a first start can take several minutes. Logs land in
`~/Library/Logs/qwen3-tts-engine.log`. `uninstall` removes the LaunchAgent but
retains the catalog, venv, and model cache.

`engines/qwen3-tts/requirements.in` records the top-level package, while
`engines/qwen3-tts/tested-constraints.txt` captures the verified environment used
to regenerate the hashed lock. Dependencies must stay hash-locked; review
changes before recompiling.

### Irodori voice registration

Irodori takes a reference WAV rather than a manifest, and its catalog is a
directory the server reads at startup — so `register` restarts the agent for
you. Reference audio and the pronunciation lexicon are private data: both are
copied into the ignored runtime directory, and neither source path may reach
tracked config.

```sh
hermes/launchd/irodori-tts-launchctl.sh install \
  --voice /absolute/path/to/reference.wav --id <voice-id>
hermes/launchd/irodori-tts-launchctl.sh register \
  --voice /absolute/path/to/another.wav --id <voice-id> --default
hermes/launchd/irodori-tts-launchctl.sh register-lexicon \
  --file /absolute/path/to/lexicon.json
hermes/launchd/irodori-tts-launchctl.sh voices
hermes/launchd/irodori-tts-launchctl.sh status
hermes/launchd/irodori-tts-launchctl.sh uninstall   # stop (plist KeepAlive)
hermes/launchd/irodori-tts-launchctl.sh purge       # + delete the runtime dir
```

`install` builds a git checkout of the upstream server plus a uv venv under the
ignored `local/irodori-tts/`; the launcher's explicit uv `--python` is mandatory,
since uv otherwise picks 3.12 and the pinned `sentencepiece` has no wheel for it. The pins file is
named `.conf` because `**/*.env` is ignored and the pins must be tracked.
`register-lexicon` validates the JSON before installing it, and refuses to
write through a symlink — that is how the private overlay owns the file. The
plugin caches the lexicon per process, so a live gateway needs a restart.

## Speech-to-text — fallback chain

STT for `default` / `assistant` runs through the `transcription/stt-fallback`
chain (`stt.provider: stt-fallback`): it tries `stt.fallback.chain` in order
(default `groq → xai → openai → elevenlabs → local`) and returns the first
successful, non-empty transcript — outage fallback, not quality fallback.
Per-tier auth:

- **groq** — `GROQ_API_KEY` (Whisper `large-v3-turbo`; fast + accurate).
- **xai** — SuperGrok OAuth (`hermes auth add xai-oauth`) or `XAI_API_KEY`.
- **openai** — `OPENAI_API_KEY` / `VOICE_TOOLS_OPENAI_KEY` (paid; skipped if unset).
- **elevenlabs** — `ELEVENLABS_API_KEY` (Scribe).
- **local** — faster-whisper; no key, offline floor (`stt.local.model: medium`,
  `stt.local.language: ''` = auto-detect).

`mistral` is excluded by default (its `mistralai` SDK was quarantined on PyPI).
Edit `stt.fallback.chain` to reorder/add/remove tiers; tiers whose credentials
are missing are skipped at runtime. STT serves the gateway (voice input) and CLI
voice mode.

## Audio hands tooling

Contracts for every audio leaf: [docs/hands/audio.md](docs/hands/audio.md).
This section only holds the maintainer commands. Run leaf helpers with the
Hermes venv Python by literal path (resolve a non-default ghq root first).

**SFX helper.** From this directory, with an existing output parent and a new
output directory:

```sh
~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python \
  profiles/audio-creator/skills/audio-creator-pipeline/scripts/sfx-media.py \
  synth --kind whoosh --seconds 0.5 --pitch 880 --seed 0 \
  --out /tmp/sfx-example --slug whoosh
```

The output directory must be new. `track`, `edit` and `analyze` document their
flags via `--help`; no command installs an engine or overwrites media.

**Local Stable Audio 3 Medium runtime** (`scripts/stable_audio3.py`, shared by
SFX and music; pins in `engines/stable-audio-3/`, install under the ignored
`local/stable-audio-3/`):

```sh
python3 hermes/scripts/stable_audio3.py install --accept-terms   # maintainer-only, once
python3 hermes/scripts/stable_audio3.py check [--full]           # readiness / drift
python3 hermes/scripts/stable_audio3.py refresh \
  --previous-adapter /absolute/path/to/previous-stable_audio3.py
```

Jobs never install or download anything. After a maintainer-only adapter
change, `refresh` verifies the old adapter fingerprint and the complete existing
installation offline before refreshing its marker. It never downloads models,
reinstalls packages, accepts new terms, or rewrites old job receipts. Drift
semantics: [docs/hands/audio.md](docs/hands/audio.md) "Local Stable Audio 3
Medium runtime".

**Mix/video integration fixture** (synthetic tones, not real speech or client
approval), from this directory with a fresh absolute output path:

```sh
~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python \
  scripts/tests/fixtures/mix-video/example.py \
  --root <new-absolute-test-directory> --freeze
```

It freezes real Mix/Ad/Tour bundles; each video leaf's snapshot/render helper
then verifies its exact test preview hashes. It proves wiring only.

Motion Canvas and Three WebGL runtimes are maintainer-provisioned from
`engines/motion-canvas/setup.mjs` / `engines/three-webgl/setup.mjs`; see
[docs/hands/video.md](docs/hands/video.md).

## Web search backends

Paid backends are pinned per profile; everyone else rides the keyless ring.

**Auto-detect.** With empty `web.search_backend` / `web.extract_backend`, Hermes
takes the first backend whose **key exists** (`exa → parallel → keenable →
firecrawl → searxng → brave-free → ddgs`), then walks the keyless tier.
Availability is key presence, never quota. Never configure a backend name that
no longer exists: it does not error, it silently resolves to `firecrawl` (and
bills researcher's credits). The Tavily backend no longer exists upstream
(`keenable` replaced it), so never configure `tavily`; a leftover
`TAVILY_API_KEY` is unused.

**Keyless ring and rescue.** Runtime failover exists only inside the free ring
(`exa → parallel → firecrawl → keenable`, `plugins/web/keyless_mcp.py` in the
agent checkout): a rate-limited keyless request advances to the next vendor, and
a failed **keyed** call gets ONE stateless keyless rescue (`web.keyless_rescue`,
default on; rescued results are never cached, so the next call retries the
profile's own backend). A keyed backend never falls through to another keyed
backend — per-profile pinning is what stops one provider's exhaustion from
taking the fleet down.

**`web.provider_tier.<vendor>` picks the lane per profile.** `free` forces the
keyless endpoint even when the key is present and pins that vendor as the ring
entry point; `paid` forces the keyed path and drops that vendor from the
profile's ring; unset = auto (key present ⇒ keyed). Editing `search_backend`
alone is not enough: with a key in the environment, auto silently bills the
paid path.

**Current split** — the three paid keys stay with the high-volume profiles;
everyone else is on the free ring with distributed entry points:

| Profile | search / extract backend | Lane |
| --- | --- | --- |
| assistant | `exa` | paid (auto, key present) |
| searcher | `parallel` | paid (auto) |
| researcher | `firecrawl` | paid (auto) |
| engineer | `exa` | `provider_tier.exa: free` |
| creator, image-creator, video-creator, audio-creator | `parallel` | `provider_tier.parallel: free` |
| writer | `firecrawl` | `provider_tier.firecrawl: free` |
| marketer | `keenable` | `provider_tier.keenable: free` |
| default | empty (neutral for `--clone`) | `provider_tier.exa: free` — otherwise auto-detect resolves to keyed Exa and spends the assistant's grant |
| ui-review, ux-persona | no `web` block | — |

`KEENABLE_API_KEY` is not set and not needed — a `free` pin resolves without one.

**Exhaustion signals** are per provider and each self-heals: Exa `402`
($10/month Free Tier grant); Firecrawl 4xx (1,000 credits/month, renews around
the 17th; balance: `GET https://api.firecrawl.dev/v2/team/credit-usage`). `401`
is a dead/rotated key, not exhaustion. Parallel's quota model is unverified (no
balance endpoint) — if searcher starts failing while the key is otherwise
valid, swap searcher and researcher (`parallel` ⇄ `firecrawl`) and update the
table above.

**Verify** a change by resolving the backend per profile
(`HERMES_HOME=~/.hermes/profiles/<p>` + `tools.web_tools._get_search_backend()`)
and by running `web_search_tool`; `data.served_by` appears only when the ring
failed over, so its absence means the pinned vendor answered. **Switch** by
editing the keys in this repo (the `~/.hermes` configs are symlinks, so a new
CLI turn picks them up); rotating an API key additionally needs a gateway
restart.

## Browser

**Routing and precedence.** With `browser.backend` unset and `uvx` present,
`browser_exec` → `uvx browser-use` → `browser_harness` attaches over CDP to the
endpoint Hermes resolves; the built-in `browser_navigate` surface and the
`browser.engine` / `camofox` keys describe the dormant path. There is no
resident CDP browser. A `BU_CDP_URL` / `BU_CDP_WS` in the **process env** wins
over everything, silently — it is copied raw from `os.environ`, so under
multiplex one value pre-empts real-profile browsing for every profile. Never add
either key to a Keychain layer the gateway launcher evals (`global`, `hermes`).
See also [engineer.md](docs/profiles/engineer.md) "UI evaluators" (native
browser tools) and [marketer.md](docs/profiles/marketer.md) "Browser lease".

**Real-profile pins.** Only profiles that need the owner's logins set
`browser.use_real_profile: true`, `real_profile_pin:` (a Brave profile
**directory** — the `Local State → profile.info_cache` key, not the display
name) and `real_profile_binary:` (the clone, `brave-agent-sync.sh path`):

| Hermes profile | `real_profile_pin` | Brave profile name |
| --- | --- | --- |
| assistant | `"Profile 12"` | Hermes Agent (Assistant) |
| marketer | `"Profile 13"` | Hermes Agent (Marketer) |

Everyone else gets upstream's on-demand packaged Chromium in a throwaway
profile. To sign an agent in, log in to services in its pinned profile in the
everyday Brave; cookies/logins are merged into
`~/.hermes/profiles/<p>/browser-profile/brave/` (ignored) on every cold clone
launch. There is no separate headful login step.

- **One Brave profile per consenting Hermes profile, never shared** — Google
  rotates its session cookies and treats an older value as a stolen session, so
  every client sharing one Google login signs the others out (static-token
  sites such as X/Instagram do not, but separate profiles still isolate their
  risk detection).
- **The owner must not browse in a pinned profile** — the owner is one more
  client of the same rotation. A pinned profile is for signing in: log in,
  close, work elsewhere. When a live clone is signed out, "log in again" in the
  everyday Brave just supersedes the clone's session and moves the sign-out.
- **Preconditions fail closed:** the macOS default browser must be Brave
  (detected from the LaunchServices `https` handler only; Safari yields none),
  the pinned profile directory must exist, and the clone binary must be
  executable.

**Why a cloned bundle.** macOS treats one app bundle as one running app, so
while a headless Brave launched from `/Applications/Brave Browser.app` is alive,
a Dock / Spotlight / `open` launch only activates it and the everyday Brave
cannot open. An APFS clone (`cp -Rc`) at another path has no shared identity,
and its untouched signature still satisfies the Keychain `Brave Safe Storage`
ACL (bundle id + team, not path), so cookies decrypt without a prompt. The clone
lives in the ignored `local/brave-agent/Brave Agent.app`.
`scripts/brave-agent-sync.sh` re-clones on version drift, and the gateway
launcher runs `sync` before every start (a stale clone keeps working until
then). **Never edit the clone** — any change breaks the signature and with it
cookie decryption; re-clone instead. `browser.real_profile_binary` is honored
only through a local patch; without it the real bundle launches and the Dock
clash returns.

**Clone lifetime.** The clone starts with `--remote-debugging-port=0` and lives
until the Hermes process that launched it exits (only the atexit hook reaps it;
the inactivity janitor closes agent-browser sessions, not this process), so one
headless Brave (expected ~230 MB) stays resident per consenting profile that has
browsed. Each Hermes home gets its own attach daemon
(`hermes-real-profile-<profile>`, pid under
`/tmp/agent-browser-hermes-real-profile-<profile>/`), and CDP calls use an owned
daemon runtime scoped by profile + logical session/task whose binding and
browser UUID are verified before code runs (local patches). Owned-daemon idle
cleanup (600 s) is opportunistic on calls and exit, not a timer, and never
refreshes cookies. Do not use the old generic `bu-default` kill workaround.
`_find_agent_browser` resolves the npx cache copy ahead of the mise shim, so the
agent-browser version on `PATH` is not necessarily the one the daemon runs.

**Cookies mirror only on a cold launch.** `snapshot_real_profile` →
`_mirror_profile_auth` runs only on the cold path of `_real_profile_cdp`; a
gateway restart finds the surviving clone via `DevToolsActivePort` and
re-attaches (`real-profile: re-attached to surviving Chrome`), mirroring nothing.
To pick up a fresh login, **relaunch the clone, not the gateway**. The cookie
store is merged row by row, newest `last_update_utc` wins, so a relaunch keeps
the clone's freshly rotated tokens (local patch; schema drift or a non-SQLite
copy falls back to overwrite). Deletions do not propagate: a sign-out in the
everyday Brave leaves the clone signed in.

**Stop the clone and its daemon together.** Upstream closes the daemon session
only when `get cdp-url` succeeds, so a daemon that outlived a killed clone keeps
the dead port, ignores the next launch's `--cdp` ("daemon already running"), and
every call fails with `All CDP discovery methods failed for 127.0.0.1:<old
port>` until the gateway restarts (unpatched upstream). The private-overlay
skill `hermes-browser-relaunch` (`scripts/relaunch.sh`) does it right: SIGTERM
clone → stop daemon → clear socket dir; it never launches — the next
`browser_exec` does. Assistant reads it through the private skills root and
Marketer through a single-skill `external_dirs` entry; each relaunches only
its own pair (Marketer while holding its browser lease). `relaunch.sh --status` prints `pages=` / `rss=` per clone.

**UA gate pages are not a relaunch case.** Sites gating on the UA string reject
headless `HeadlessChrome/<v>`, so the headless launch passes `--user-agent` with
the binary's major version (local patch; unreadable version → no flag; headed
untouched; UA-CH brands become empty). An "update your browser / unsupported
browser" page is a UA gate — never a relaunch case and never evidence that the
owner's login expired. `Browser.getVersion` reports `Chrome/…` on Brave: check
the process, not the product string, to know which browser answered.

**Session-restore purge.** The long-lived copy directory would let Chromium's
ordinary session restore replay old tabs into every new clone, compounding until
the browser wedges; `_launch_real_profile_chrome` purges `<profile>/Sessions`
before launch and `Sessions` is in `_SNAPSHOT_IGNORES` (local patch). It is not
crash restore (`exit_type` is no signal), and tab growth is launcher state, not
agent behavior — never try to fix it with prompt-side rules. Rising `pages=` /
`rss=` in `relaunch.sh --status` means the purge went missing.

**IndexedDB-backed logins.** The snapshot excludes `IndexedDB` (it wedges a
fresh renderer and costs hundreds of MB) and only auth DBs re-sync per launch,
so a site that keeps its session there (WhatsApp Web) arrives signed out even
when the everyday Brave is signed in. Such a site needs its own login **in the
clone** (WhatsApp: pair it as a separate linked device from the QR page); that
state persists across relaunches but not across a snapshot rebuild or
`use_real_profile` going off. **Never copy IndexedDB across profiles** — for
WhatsApp that shares one linked-device identity between two clients, the same
failure as a shared Google session.

The worker-facing rule (spawn your own browser with port 0, never attach to
Hermes' instance) lives in `~/Workspaces/AGENTS.md` (private overlay).

## Worker terminal approvals

Dispatcher workers cannot answer an approval prompt — a flagged command just
fails. The dispatcher runs workers with `stdin=DEVNULL` but still sets
`HERMES_INTERACTIVE=1`, so `approvals.mode: manual` reaches EOF, denies, and the
tool returns `status: "blocked"`.

- **The guard reads only the outer command**, never inside a script. These pass:
  `./scripts/x.sh`, `bash x.sh`, `python3 script.py`, `opencode run`,
  `npx hyperframes …`, `ffmpeg`, `git commit`, non-force `git push`,
  `gh pr create`, `xurl`.
- **What trips it:** inline interpreters (`bash -c`, `python3 -c`, `node -e`),
  `find -delete`, `chmod +x … && ./…`, recursive `rm -rf`, `git reset --hard`,
  `git clean -f`, force push. Write worker playbooks around scripts and wrapper
  CLIs, never inline one-liners.
- **`command_allowlist` stays empty on purpose.** It is the escape hatch (exact
  match or fnmatch glob against the whole command; skipped when the command
  contains `&&` `|` `>` `;`), and allowing e.g. `bash -c *` would reopen exactly
  what the guard exists to catch.
- The hardline floor (`rm -rf /`, `$HOME`, system dirs) blocks regardless.

## Commands

**Setup and upkeep**

- `./setup.sh` — install/refresh the hermes binary (uv venv); idempotent.
- `../install.sh` — create the `~/.hermes/` symlinks (run after adding files).
- `hermes update` — git pull + re-sync (use this to update, not `setup.sh`);
  afterwards follow the post-update sequence in [`AGENTS.md`](AGENTS.md)
  (local patches, validator, seeded skill roots — see [Skills](#skills)).
- `./scripts/check-local-patches.sh [hermes-agent-dir]` — every local `fix/*`
  branch in the hermes-agent checkout must be merged into `local`, and the
  case-collision twin must keep `skip-worktree`; exit 1 names what is missing.
  `git checkout --` does not fix that twin (it only flips which twin is dirty).
- `hermes doctor` — validate providers / model tiers.

**Validation and tests**

- `./scripts/validate-profile-skills.py --all` — validate managed/learned skill
  topology, metadata, routing registries, hands leaves, Creator's phase/subject
  references and Git ownership; add `--strict-git` in a staged/clean tree to
  fail on managed files that are still untracked.
- Full suite:
  ```sh
  PYTHONPATH=$(ghq root)/github.com/NousResearch/hermes-agent \
    $(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python -m pytest \
    plugins/ scripts/tests/ -q --import-mode=importlib
  ```
  The Hermes venv is required (plugins import `agent.*` / `tools.*`), and
  `--import-mode=importlib` is not optional: every plugin keeps its suite at
  `tests/test_plugin.py`, those basenames collide under the default import mode,
  and `__init__.py` cannot fix it because the hyphenated plugin directories are
  not importable package names.
- `scripts/verify-work-continuity.py --runtime <hermes-agent-checkout>
  --private <paired-private-checkout>` — run with the provisioned Hermes Python
  before cutover and after an upstream update. It runs the strict Git/topology
  validator, paired public/private tests and runtime regressions; it never
  installs, restarts or migrates jobs.
- Entry-runtime suites in `scripts/tests/` (provisioned Hermes Python, explicit
  source `PYTHONPATH`, isolated HOME, no network; registered in
  `verify-work-continuity.py`): `test_{engineer,creator,marketer,searcher,writer,assistant}_entry_runtime.py`,
  `test_creator_entry_contract.py`, `test_hands_instruction_context.py`,
  `test_marketer_{pipeline,browser_lease}.py`, `test_researcher_entries.py`,
  `test_searcher_pipeline.py`; run `test_media_craft_routing.py` and
  `test_audio_creator_routing.py` with the hands tests. What they prove:
  [docs/topology.md](docs/topology.md) "Candidate rollout and cutover".
- Paired candidate selectors: set `HERMES_PRIVATE_ROOT=<private-checkout>` on
  public tests and `HERMES_PUBLIC_ROOT=<public-checkout>` on private tests.
  These select source trees for tests, not runtime wiring. Never run install
  scripts or create live links for candidate checks, and never weaken live
  Git/symlink ownership checks.

**Services** (LaunchAgents; host-rendered plists land in
`~/Library/LaunchAgents/`, never committed)

- `launchd/gateway-launchctl.sh {install,status,uninstall}` — the multiplex
  gateway LaunchAgent (`local.hermes.gateway.multiplex`), **one host only** (one
  bot token = one live connection; four bots in this one process). The
  default-hosted process serves assistant Telegram + Discord, the engineer /
  creator / marketer bots, the A2A endpoints (`127.0.0.1:9902-9909`) and the
  embedded dispatcher; `install` also unloads the legacy
  `local.hermes.gateway.assistant` agent. `install` re-renders + reloads =
  **restart**; `/restart` in chat also applies config (drain → `KeepAlive`
  respawns one). **Stop = `uninstall`** (`KeepAlive:true`; a plain `kill` just
  respawns). **Never** run `hermes gateway run`/`restart` in a terminal while it
  is loaded — a second poller causes Telegram `getUpdates` 409 conflicts
  (`pgrep -fl 'gateway run'` ⇒ exactly 1). Design:
  [docs/operations.md](docs/operations.md) "Gateway as a persistent service".
- `launchd/qwen3-tts-launchctl.sh {install,register,unregister,voices,status,uninstall}`
  — Qwen3-TTS on `:10102`; see [Qwen3-TTS voice catalog](#qwen3-tts-voice-catalog).
- `launchd/irodori-tts-launchctl.sh {install,register,register-lexicon,voices,status,uninstall,purge}`
  — Irodori-TTS on `:10103`; see [Irodori voice registration](#irodori-voice-registration).
- `scripts/brave-agent-sync.sh {sync,check,path,remove}` — the real-profile
  Brave clone ([Browser](#browser)). `sync` (default) re-clones when
  `/Applications/Brave Browser.app` changed version or the clone is missing,
  terminating a running clone first (the gateway launcher runs it before every
  start; run it by hand after a Brave update rather than wait); `check` exits 0
  when the clone matches; `path` prints the `real_profile_binary` value;
  `remove` deletes the clone and any running instance.
