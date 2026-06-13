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
| `~/.hermes/skills`      | `hermes/skills/`    |

### Skills — agent-created are tracked, bundled are not

`~/.hermes/skills` is symlinked to the repo, so **skills the agent creates land
in `hermes/skills/`** and are version-controlled (the agent always writes new
skills to `HERMES_HOME/skills`). The ~73 **bundled** skills are kept out of the
repo: seeding is disabled — `hermes skills opt-out --remove` writes a
`.no-bundled-skills` marker, which is tracked here and symlinked into
`~/.hermes/` by `install.sh` so the opt-out reproduces on a fresh machine — and
`config.yaml` points `skills.external_dirs` at the agent clone
(`~/ghq/github.com/NousResearch/hermes-agent/skills`), so they're read in place
(read-only, auto-updated by `hermes update`). Curator/hub/usage bookkeeping
(`.curator_state`, `.hub/`, `.usage.json`, `.archive/`, …) lands in
`hermes/skills/` but is git-ignored.

### Cron — job definitions tracked, runtime churn ignored

`~/.hermes/cron` is symlinked to `hermes/cron/`. Hermes stores every job in a
single `cron/jobs.json` (definition **and** run-state in one file), which is
tracked — churn is occasional unless a gateway runs cron continuously. The
per-run logs (`cron/output/`) and scheduler lock (`cron/.tick.lock`) are
git-ignored.

## User-managed content

- `config.yaml` — model/provider, terminal backend, memory, compression,
  toolsets, `skills.external_dirs`. No secrets. Hermes rewrites this on load.
- `SOUL.md` — global agent identity (system-prompt slot #1).
- `mcp.json` — MCP server connections.
- `skills/<name>/SKILL.md` — version-controlled skills (agent-created land here;
  bundled are read from the clone via `external_dirs`, not tracked).
- `cron/jobs.json` — scheduled job definitions (run-state churns in the same
  file; `cron/output/` and `cron/.tick.lock` are git-ignored).

## Profiles

Named profiles live under `~/.hermes/profiles/<name>/` — each its own
`HERMES_HOME` with its own `config.yaml` / `.env` / `SOUL.md` / `skills/` /
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
2. Stop bundled-skill seeding so only agent skills get tracked:
   ```sh
   hermes -p <name> skills opt-out --remove --yes
   ```
3. Move the version-controllable files into the repo (skip any that don't exist):
   ```sh
   mkdir -p ~/.config/hermes/profiles/<name>
   mv ~/.hermes/profiles/<name>/{config.yaml,SOUL.md,mcp.json,cron,skills} \
      ~/.config/hermes/profiles/<name>/
   ```
4. In that profile's tracked `config.yaml`, point `skills.external_dirs` at the
   clone (`~/ghq/github.com/NousResearch/hermes-agent/skills`) — same as default.
5. `./install.sh` — the `[hermes]` loop now symlinks them (no WARN).

State (`.env`, `memories/`, `sessions/`, `state.db*`, …) stays in
`~/.hermes/profiles/<name>/` — never moved, never tracked.

### Caveats

- **Order matters / "already installed".** The symlink must exist *before*
  Hermes writes a real file. If real files already exist (a named profile, or a
  `~/.hermes/` set up before this repo), `install.sh` won't replace them — use
  the move-then-`install.sh` adoption above. Hermes itself still runs fine
  either way; only the symlink tracking is affected.
- **Per-profile secrets aren't isolated by the shim.** The wrapper always calls
  `hermes`, so every profile gets the same `global` + `hermes` layers.
  Profile-specific secrets (e.g. a distinct `TELEGRAM_BOT_TOKEN`) go in that
  profile's own `~/.hermes/profiles/<name>/.env` (untracked).
- **Background / launchd profiles** (`hermes gateway install`) may run with a
  PATH that excludes `~/.config/bin` and a locked Keychain, so the shim can't
  inject — those rely on the profile `.env`.

## Secrets

No `.env` files. API keys live in the macOS Keychain and are injected at launch
by the [`bin/hermes`](../bin/secret-shim) secret-shim (`secret env -p global`
then `secret env -p hermes`). Shared keys (e.g. `OPENROUTER_API_KEY`) go in the
`global` layer; Hermes-only keys (e.g. `TELEGRAM_BOT_TOKEN`, `FAL_KEY`,
`BROWSERBASE_API_KEY`) go in the `hermes` layer. See
[`secret`](../zsh/functions/secret.md).

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
secret set OPENROUTER_API_KEY -p global   # model + moa + vision fallback (shared)
secret set GITHUB_TOKEN       -p global   # Skills Hub rate limits (shared)
secret set EXA_API_KEY        -p hermes   # web_search / web_extract
secret set GROQ_API_KEY       -p hermes   # cloud STT (local faster-whisper needs no key)
```

Other optional keys (`-p hermes` unless shared): `FAL_KEY` (image_gen),
`ELEVENLABS_API_KEY` (premium TTS), `XAI_API_KEY` (x_search / video_gen),
`BROWSERBASE_API_KEY` (cloud browser), `TELEGRAM_BOT_TOKEN` /
`DISCORD_BOT_TOKEN` (gateway). STT/TTS default to free local `faster-whisper` +
Edge TTS in `config.yaml`.

## Never tracked

Per-machine state stays in `~/.hermes/`: `.env`, `auth.json`, `memories/`,
`sessions/`, `state.db*`, `logs/`, `workspace/`, `plans/`, `*_cache/`, `local/`.
