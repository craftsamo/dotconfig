# Hermes Agent

Self-improving AI agent CLI by Nous Research. Hermes keeps everything under
`~/.hermes/` (it does **not** read `~/.config` natively), so
[`install.sh`](../install.sh) symlinks the version-controlled, non-secret files
into place.

## Specialist Calls

The shared `plugins/specialist-call` plugin exposes the `specialist` toolset
only to assistant and creator. Enable `specialist-call` in `plugins.enabled`
and `specialist` in the relevant `platform_toolsets` lists. Configure the
explicit `specialist_call.resident_targets` allowlist; short inquiries use an
allowed target's existing `a2a_agents` RPC endpoint when present. No endpoint
is discovered from model text or a supplied URL. Work always uses the existing
resident script. Creator currently has no configured A2A peers, so its
researcher calls use resident sessions; its dormant messaging lists stay empty.

Use `specialist_call(target, message, kind="inquiry"|"work")`, then continue
with the returned `conversation_id`. `specialist_session` supports `status`,
`list`, and `close` in the same originating session and profile. The registry
and restrictive request files live under that caller's real Hermes home in
`specialist-sessions/`; resident JSON and logs retain the existing format in
`resident-sessions/`. Old resident keys remain runnable through the original
script. Automatic adoption is intentionally unsupported because old entries
do not establish an originating-session owner.

Verified live Telegram/Discord contexts use the official terminal background
completion notification. The current single-profile gateway verifies its
process home against the plugin's registered profile; multiplex gateways must
provide an explicit task-scoped home. Unbound routing or ambiguous multiplex
flags fail closed. CLI, including creator nested under assistant's resident
child, waits for a short-lived runner with a maximum 5400-second deadline.
Nested calls inherit the outer wall-clock deadline rather than resetting it.
If the caller dies, the runner terminates its resident process group, preserves
an `unknown` result, and exits. This covers caller death, not simultaneous
termination of the runner itself or descendants that deliberately leave the group.
A2A inbound permits only synchronous A2A inquiries and rejects work before
launch. `close` is bookkeeping, not cancellation. An uncertain transport result
or an interrupted runner is never retried, reclaimed, or moved to another
backend automatically: inspect retained status/logs and reconcile manually.
Proven pre-dispatch failures (including terminal rejection, invalid request
configuration, DNS/refused connections, and spawn failures) are `failed` and
closable even when no resident session exists. Ambiguous launches retain their
request file and become `unknown`; they cannot be closed or retried. Listing
conversations skips revoked targets without hiding other permitted rows.
This is not a durable queue; notification delivery does not survive every
gateway restart. Resident polling defaults to one second; the upstream
completion watcher still polls every five seconds.

Gateway ownership uses the framework-dispatched agent session ID and the
gateway turn's session ID, not a model argument or process environment fallback.
The dispatched ID is bound task-locally for the official notification stamp too;
cached turns work even when gateway setup leaves the ID ContextVar empty, and
resetting a chat does not grant access to its previous specialist conversations.
The resident script exits `143` on INT/TERM with `status: interrupted` and
retained partial logs/session identity. Exit `124` denotes deadline expiry;
neither interruption is proof of successful completion.

## Default profile symlinks

| Symlink                 | Target              |
| ----------------------- | ------------------- |
| `~/.hermes/config.yaml` | `hermes/config.yaml` |
| `~/.hermes/SOUL.md`     | `hermes/SOUL.md`    |
| `~/.hermes/mcp.json`    | `hermes/mcp.json`   |
| `~/.hermes/skills`      | `hermes/skills/`    |
| `~/.hermes/plugins`     | `hermes/plugins/`   |

### Skills — managed core tracked, learned library ignored

`~/.hermes/skills` is symlinked to the repo. The maintainer-owned shared
`default-pipeline/` CLI adapter is version-controlled; the assistant's
`assistant-pipeline` lives under its profile and owns the shared reference
tree — its content sits in the private overlay, reached through a symlink at
`profiles/assistant/skills/assistant-pipeline` (as do the `desks/`).
The ~/Workspaces data-skill
cluster lives in the private overlay (this repo is public) and is read through
`skills.external_dirs` as `~/.config/private/hermes/skills`. Runtime-authored
skills are mutable state under `learned/` and are git-ignored. The
`skill-topology` plugin rewrites every normal `skill_manage(action=create)`
call — including background review, curator and `/learn` — to
`HERMES_HOME/skills/learned/<name>`. The ~73 **bundled** skills are also kept
out of the repo: seeding is disabled — `hermes skills opt-out --remove` writes a
`.no-bundled-skills` marker, which is tracked here and symlinked into
`~/.hermes/` by `install.sh` so the opt-out reproduces on a fresh machine — and
`config.yaml` points `skills.external_dirs` at the agent clone
(`~/ghq/github.com/NousResearch/hermes-agent/skills`), so they're read in place
(read-only, auto-updated by `hermes update`). Curator/hub/usage bookkeeping
(`.curator_state`, `.hub/`, `.usage.json`, `.archive/`, …) lands in
`hermes/skills/` but is git-ignored.

### Cron — machine-local, outside the repo

`~/.hermes/cron` (and each profile's) is a real directory this repo neither
links nor tracks. Hermes creates it and owns every file in it: `jobs.json`,
`output/`, `executions.db`, `.tick.lock`, `.jobs.lock`, `ticker_*`,
`catch_up_occurrences`, `suggestions.json`. Because definition and run-state
share one file, tracking `jobs.json` meant either constant churn or a
`skip-worktree` flag that hid new jobs and broke branch switches — so the whole
directory stays out.

Nothing recreates a lost `jobs.json`; Hermes reads a missing one as zero jobs
without warning. The private `local-*` schedules are re-creatable from the
`hermes cron create` commands in the private overlay's README
(`~/.config/private`, the `private-dotconfig` repo).

### Plugins — provider chains & tool overrides

`~/.hermes/plugins` is symlinked to `hermes/plugins/` (and into each profile's
home — plugin discovery is `HERMES_HOME`-scoped). Plugin **source is tracked**;
Python bytecode (`**/__pycache__/`, `*.pyc`) is git-ignored. The whole dir is
symlinked, so a new plugin needs no re-`install.sh` — only `plugins.enabled` in
the relevant `config.yaml`.

- **image_gen / video_gen fallback chains** (`kind: backend`):
  `image_gen/image-fallback` registers `img-codex-xai` (Codex → xAI),
  `img-xai-codex-fal` (xAI → Codex → FAL), and `img-codex-xai-fal`
  (Codex → xAI → FAL); Creator uses the Codex-first `img-codex-xai-fal` chain.
  `video_gen/video-fallback` registers `vid-xai-fal` (Grok Imagine → FAL) and the
  reverse `vid-fal-xai`. Pick one per profile via `image_gen.provider` /
  `video_gen.provider`.
- **video-analyze-mimo** (`kind: standalone`): overrides the built-in
  `video_analyze` to route video understanding to a fixed, config-driven backend
  (`video_analyze: {provider, model}`, default OpenRouter / `xiaomi/mimo-v2.5`),
  bypassing `auxiliary.vision`. This lets `auxiliary.vision` stay `auto` so images
  route natively to the active main model while video always lands on a
  video-capable backend.
- **tts/irodori-tts** (`kind: backend`): Irodori-TTS client for the loopback
  server on `127.0.0.1:10103`. Japanese only — it refuses English-dominant text
  so the chain advances — and it rewrites Latin proper nouns from a private
  lexicon and repairs its own output before delivery
  (see [Local TTS engines](#local-tts-engines)).
- **tts/qwen3-tts** (`kind: backend`): registered-voice Qwen3-TTS client for the
  loopback server on `127.0.0.1:10102`. The multilingual tier, and the one that
  takes whatever Irodori declines (see [Local TTS engines](#local-tts-engines)).
- **tts/character-voice** (`kind: standalone`): the two Creator-only character
  voice tools. It owns no backend: it resolves an engine out of the TTS registry
  and calls it directly, so a named character asset never routes
  (see [Character voices](#character-voices)).
- **tts/tts-fallback** (`kind: backend`): TTS fallback chain. Tries
  `tts.fallback.chain` in order (`irodori-tts → qwen3-tts → edge`) and returns
  the first tier that produces audio, so a down local server still speaks
  (Edge TTS, `tts.edge.voice: ja-JP-NanamiNeural`). Active via
  `tts.provider: tts-fallback`.
- **transcription/stt-fallback** (`kind: backend`): STT fallback chain. Tries
  `stt.fallback.chain` in order (default `groq → xai → openai → elevenlabs →
  local`) and returns the first successful transcript. Active via
  `stt.provider: stt-fallback` (see [Speech-to-text](#speech-to-text--fallback-chain)).
- **skill-topology** (`kind: standalone`): request middleware that forces new
  runtime-authored skills into `learned/`. It does not intercept dashboard
  direct-create APIs or arbitrary terminal/file writes; the topology validator
  catches those paths after the fact.

## User-managed content

- `config.yaml` — model/provider, terminal backend, memory, compression,
  toolsets, `skills.external_dirs`, media backends (`image_gen` / `video_gen` /
  `video_analyze` providers, `auxiliary.vision`). No secrets. Hermes rewrites
  this on load.
- `SOUL.md` — global agent identity (system-prompt slot #1).
- `mcp.json` — MCP server connections.
- `skills/default-pipeline/` — the version-controlled thin CLI adapter for the
  default profile. Its reference source is
  `profiles/assistant/skills/assistant-pipeline/references/`, whose mode-first
  tree owns the front-door workflow and quality-assurance contracts.
  The closed kanban catalog is the union of `card_units` front matter across
  `execute/**` (each unit names its `assignee` worker); topology, routing,
  schema, required QA contracts, and the worker-kernel unit-gate parity are
  enforced by `scripts/validate-profile-skills.py`.
  The ~/Workspaces data-skill cluster lives in the private overlay, read
  through `skills.external_dirs` as `~/.config/private/hermes/skills`.
  `skills/learned/` is the untracked adaptive library; bundled skills are read
  from the clone via `external_dirs`.

## Profiles

Named profiles live under `~/.hermes/profiles/<name>/` — each its own
`HERMES_HOME` with its own `config.yaml` / `SOUL.md` / `skills/` /
`cron/`. The alias `~/.local/bin/<name>` is just a wrapper that runs
`exec hermes -p <name> "$@"` — **bare `hermes`**, so it still resolves through
the `bin/hermes` shim and the shared `global` + `hermes` Keychain keys are
injected for every profile.

### Tracking a profile

`install.sh`'s `link()` never overwrites a real file — it prints
`WARN … not overwriting` and skips (the repo-wide drift policy). Because
`hermes profile create` writes **real** files into `~/.hermes/profiles/<name>/`,
move them into the repo (clearing the real files) before linking:

1. `hermes profile create <name>` — seeds state + the `~/.local/bin/<name>` alias.
2. Stop bundled-skill seeding so bundled skills stay in `external_dirs`:
   ```sh
   hermes -p <name> skills opt-out --remove --yes
   ```
3. Move the version-controllable files into the repo (skip any that don't exist):
   ```sh
   mkdir -p ~/.config/hermes/profiles/<name>
   mv ~/.hermes/profiles/<name>/{config.yaml,profile.yaml,SOUL.md,mcp.json,cron,skills} \
      ~/.config/hermes/profiles/<name>/
   ```
4. In that profile's tracked `config.yaml`, point `skills.external_dirs` at the
   clone (`~/ghq/github.com/NousResearch/hermes-agent/skills`) — same as default.
5. `./install.sh` — the `[hermes]` loop now symlinks them (no WARN).

State (`memories/`, `sessions/`, `state.db*`, …) stays in
`~/.hermes/profiles/<name>/` — never moved, never tracked.

Each worker profile tracks exactly one `<profile>-pipeline/` and a `technic/`
directory. Pipelines implement the shared `admit → route → act_or_plan → verify
→ handoff → terminal` lifecycle; Workers never register Kanban cards. The
assistant keeps `technic/` here, while its `desks/` and `assistant-pipeline/`
are private-overlay symlinks (personal messaging operation; content tracked by
the private-dotconfig repo); `default-pipeline` adapts that tree for the CLI. Every profile may grow an
untracked `learned/` library. To promote a learned skill, review it, move the
complete package into `technic/`, set `metadata.hermes.category: technic`, add
it to the pipeline's capability registry when applicable, pin an agent-created
source with `hermes -p <profile> curator pin <name>`, then commit it normally.

### Caveats

- **Order matters / "already installed".** The symlink must exist *before*
  Hermes writes a real file. If real files already exist (a named profile, or a
  `~/.hermes/` set up before this repo), `install.sh` won't replace them — use
  the move-then-`install.sh` adoption above. Hermes itself still runs fine
  either way; only the symlink tracking is affected.
- **Per-profile secrets aren't isolated by the shim.** The wrapper always calls
  `hermes`, so every profile gets the same `global` + `hermes` Keychain layers.
  If a profile needs isolation, add a dedicated Keychain injection path rather
  than introducing `.env` files.
- **Background / launchd profiles** may start with a restricted `PATH`. The
  tracked Assistant gateway launcher sets `PATH` explicitly and injects the
  approved Keychain layers before `exec`; other services must follow the same
  pattern.

## Secrets

No `.env` files. API keys live in the macOS Keychain and are injected at launch
by the [`bin/hermes`](../bin/secret-shim) secret-shim (`secret env -p global`
then `secret env -p hermes`). The `hermes` layer holds keys only Hermes uses
(e.g. `OPENROUTER_API_KEY`, `GITHUB_TOKEN`) — it's injected for every `hermes`
invocation, including every profile alias (`~/.local/bin/<name>` runs bare
`hermes -p <name>`). The `global` layer is for keys shared with other shimmed
tools. See [`secret`](../zsh/functions/secret.md).

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
separately for the `~/.hermes/` config symlinks, and store keys with
`secret set …` (no `.env`).

## Capabilities & dependencies

Maximal CLI setup — what enables each tool group:

**System packages** (declared in the [Brewfile](../Brewfile)):

- `ffmpeg` — TTS / voice audio conversion (all platforms)
- `portaudio` — CLI voice mode microphone input + playback
- `opus` — Discord voice-channel codec

The local `browser` toolset already works via `agent-browser` + Playwright
Chromium (from mise) — no Browserbase key needed.

**`cua-driver`** (the macOS `computer_use` toolset — background desktop control)
has no Brewfile formula and needs one-time GUI grants:

```sh
hermes computer-use install      # fetches trycua/cua -> ~/.local/bin/cua-driver
cua-driver permissions grant     # grant Accessibility + Screen Recording
hermes computer-use status       # verify
```

`hermes update` refreshes the driver automatically when it's on `PATH`.

**API keys** — stored in the Keychain; the `bin/hermes` shim injects them (no
`.env`). Run these yourself (the value is read from stdin, never argv):

```sh
secret set OPENROUTER_API_KEY -p hermes   # T3 fallback + moa + vision + video analysis (mimo)
secret set GITHUB_TOKEN       -p hermes   # Skills Hub
secret set EXA_API_KEY        -p hermes   # web_search / web_extract
secret set GROQ_API_KEY       -p hermes   # cloud STT (local faster-whisper needs no key)
```

Other optional keys (`-p hermes` unless shared): `FAL_KEY` (image + video
generation fallback), `ELEVENLABS_API_KEY` (premium TTS), `XAI_API_KEY`
(x_search / video_gen),
`BROWSERBASE_API_KEY` (cloud browser), `TELEGRAM_BOT_TOKEN` /
`DISCORD_BOT_TOKEN` (gateway). Voice runs through fallback chains: TTS is
`tts-fallback` (`irodori-tts → qwen3-tts → edge`) and STT is `stt-fallback`
(`groq → xai → openai → elevenlabs → local`). See the local TTS and
Speech-to-text sections below.

## Local TTS engines

Two loopback-only engines run as LaunchAgents and take no API key:
`irodori-tts` on `127.0.0.1:10103` and `qwen3-tts` on `127.0.0.1:10102`. The
chain is `irodori-tts → qwen3-tts → edge`, and there is no router in front of
it — Irodori is Japanese-only and *declines* text under 20% kana/kanji by
raising, which is what promotes an English-dominant line to Qwen3. Measured on
English-only text, Irodori scores 27% word error rate against Qwen3's 8%.

The hand-off is per utterance on purpose. The same reference voice renders 309
cents apart on the two engines, against 20-40 cents of seed-to-seed variation,
so splicing them inside one sentence is audible. For anything longer than a
chat reply, pin the engine instead (see [Character voices](#character-voices)).

Irodori runs fp32 on MPS — bf16 is CUDA/XPU-only upstream — from a git checkout
pinned in `irodori-tts/pinned.conf`. It rewrites Latin proper nouns to katakana
through a private pronunciation lexicon, then repairs its own WAV before
delivery: the in-pause codec rustle is gated, leading dead air and trailing
hallucinated fragments are trimmed, the onset click is faded and the level is
normalised. That repair uses numpy and the stdlib only, because the Hermes venv
carries no soundfile or scipy.

Irodori also performs emoji as non-verbal vocalisations and accepts a free-text
delivery caption, but only the explicit character-voice contract reaches those —
see [Performance direction](#performance-direction).

Normal speech omits a voice ID and uses each engine's default. When a server is
unavailable or still loading, `tts-fallback` advances to the next tier and
finally to Edge TTS (`ja-JP-NanamiNeural`); the call only errors if every tier
fails. Auto-speech (`voice.auto_tts: true`, set for `default` + `assistant`) is
voice-in → voice-out in the gateway and TTS-on-by-default inside CLI voice
mode — it never auto-speaks plain text turns. After changing a live config,
restart the relevant Hermes process (e.g. the gateway) to apply it.

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
repo. A manifest location is supplied only during machine-local registration:

```text
/absolute/path/to/voice.json
```

Each manifest contains the voice id, language, model revision, generation seed,
and paths to the approved reference audio/transcript. It also pins both
reference SHA-256 digests and the PCM WAV metadata. Reference paths are relative
to the manifest, so the character tree can move as one unit. The reference
transcript and audio drive in-context cloning, which carries the reference's
prosody into synthesis — an expressive, natural reference is the primary lever
for output intonation.

A manifest may add an optional `pronunciation.lexicon` entry (`path` +
`sha256`) pointing to a JSON object of surface-form → reading substitutions.
The server applies the lexicon (longest surface first) after whitespace
normalization and before synthesis; use it to pin down words the model
misreads, not to rewrite whole sentences into kana. Long inputs are split into
sentence-aligned chunks (~200 chars, clause fallback), each chunk is generated
with the manifest seed re-applied, and the chunks are joined with a 150 ms
gap — this stabilizes intonation and avoids the known Japanese end-of-text
truncation.

The first install registers the default voice. Additional characters can be
registered by manifest without adding ports, providers, or LaunchAgents:

```sh
hermes/launchd/qwen3-tts-launchctl.sh install \
  --voice-manifest /absolute/path/to/voice.json
hermes/launchd/qwen3-tts-launchctl.sh register \
  --voice-manifest /absolute/path/to/another-voice.json
hermes/launchd/qwen3-tts-launchctl.sh register \
  --voice-manifest /absolute/path/to/another-voice.json --default
hermes/launchd/qwen3-tts-launchctl.sh unregister --voice another-voice
hermes/launchd/qwen3-tts-launchctl.sh voices
hermes/launchd/qwen3-tts-launchctl.sh install  # reuses the local catalog
hermes/launchd/qwen3-tts-launchctl.sh status
hermes/launchd/qwen3-tts-launchctl.sh uninstall
```

When authoring a new manifest, validate it standalone before registering:
`python3 hermes/scripts/qwen3_tts_server.py check-manifest /path/to/voice.json`.

To find misreadings before they surface in conversation, run the round-trip
checker against the live server: `hermes/scripts/qwen3_tts_reading_check.py
--text "…"` (or `--file corpus.txt`). It synthesizes each sentence,
transcribes it with faster-whisper, compares expected and heard readings in
kana, and prints paste-ready lexicon candidates. Findings are candidates, not
verdicts — ASR can mask real errors or mishear correct ones, so confirm by
ear (`--keep-audio DIR` keeps the wavs) before adding an entry to the voice's
pronunciation lexicon and re-running `install`. The script resolves its own
dependencies through `uv run`; the server venv stays untouched.

`install` creates an isolated Python 3.12.11 venv under the ignored
`hermes/local/qwen3-tts/`, stores absolute private manifest locations only in the
ignored `catalog.json`, synchronizes the hash-locked
`qwen3-tts/requirements.lock`, validates every manifest, renders the LaunchAgent,
and atomically activates the catalog. A failed registration, service load, or
identity-bound health check restores the previous catalog and service. The
tracked plist contains only the stable ignored catalog path. An existing
single-voice `voice.json` registration is migrated automatically on the first
catalog install. Model weights are cached below the same ignored directory. A
first start can take several minutes; later starts reuse the cache. Logs land in
`~/Library/Logs/qwen3-tts-engine.log`. `uninstall` removes the LaunchAgent but
retains the catalog, venv, and model cache.

`qwen3-tts/requirements.in` records the top-level package, while
`qwen3-tts/tested-constraints.txt` captures the verified environment used to
regenerate the hashed lock. Review dependency changes before recompiling it.

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

`register-lexicon` validates the JSON before installing it, and refuses to
write through a symlink — that is how the private overlay owns the file. The
plugin caches the lexicon per process, so a live gateway needs a restart.

## Character voices

Creator — and only Creator — gets `character_voices` and
`character_text_to_speech` from the `tts/character-voice` plugin. They exist to
render a *named* asset, which is the opposite contract from ordinary speech:
the caller pins the sound, so nothing routes, nothing substitutes, and a
refusal writes no file.

`character_voices` lists every voice registered on a live engine, each as a
qualified `<engine>:<voice-id>`. Reference-free entries an engine may advertise
are filtered out — their timbre changes per run, so they are not characters.
Pass one id verbatim to `character_text_to_speech`.

A bare voice id is rejected. The engine is half of what identifies a sound: the
same reference renders 309 cents apart on the two engines, so `<voice-id>`
alone under-specifies the request. That also makes the qualified id the right
value for a `tts-voice` card's voice preset, since it survives as a durable,
unambiguous name for the sound that was approved.

Failures stay failures. A voice that is not registered on the named engine, a
stopped engine, and Irodori refusing English-dominant text all come back as
errors naming the engine — never as a quiet render by the other one.

### Performance direction

Each engine reports the style controls it honours, and the tool refuses one the
named engine does not list rather than dropping it quietly — a silently ignored
direction returns a file that is not the take that was asked for. Irodori lists
all three; Qwen3 lists none.

**Emoji become performance, not words.** On an engine listing `emoji`, an emoji
in the script is acted out where it stands — 🤭 a stifled laugh, 😭 sobbing, 🎵
humming, 😠 a sulk — and is never read aloud. The script is still cleaned the
usual way (markdown, units, newlines); the clusters are parked through that pass
and restored, so nothing else changes. Everywhere else emoji are stripped as
before. Spend them sparingly: one 🤭 measured **+1.68 s** of added audio on a
5.24 s line.

**`style` directs the whole take.** A free-text direction in the language of the
script (`落ち着いた低い声で、ゆっくりと話す`) shapes pace and manner while the
reference keeps the voice's identity. Measured, the wording is obeyed — *ゆっくり*
ran +0.56 s and *早口で* −0.32 s on the same sentence.

**`seed` means the caller can pin one, not that the engine is otherwise
random.** Irodori draws a fresh seed per request when left alone — three unpinned
renders of one line came back as three different takes — so the tool always pins
one, generating it when the caller does not, and returns it with the result.
Re-rendering that script with that seed rebuilds the same audio, post-processing
included. Qwen3 exposes no seed because its server already fixes one per voice:
an identical request reproduces on its own (three renders, one hash), and there
is nothing for the caller to vary or record. What a seed buys is rebuilding *that
take* from the same request — making a **different** line match an approved one
is continuity work it does not buy. Compare decoded samples, not file hashes: the
WAV comes back byte-identical, but the delivered Ogg carries a randomly generated
bitstream serial, so two identical takes differ in ~80 container bytes.

Ordinary chat speech is untouched by all of this: `tts.fallback.chain` passes no
style arguments, so it sends the request it always did — which on Irodori means
an unpinned, freshly rolled take per call, exactly as before.

## Speech-to-text — fallback chain

STT for `default` / `assistant` runs through the
[`transcription/stt-fallback`](#plugins--provider-chains--tool-overrides) chain
(`stt.provider: stt-fallback`): it tries `stt.fallback.chain` in order (default
`groq → xai → openai → elevenlabs → local`) and returns the first successful,
non-empty transcript — outage fallback, not quality fallback. Per-tier auth:

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

## Never tracked

Per-machine state stays in `~/.hermes/`: `auth.json`, `memories/`,
`sessions/`, `state.db*`, `logs/`, `workspace/`, `plans/`, `*_cache/`, `local/`.
