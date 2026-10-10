# Install and dependencies

How the Hermes binary is installed, how secrets reach it, how the web dashboard
is exposed on the tailnet and which system packages and keys the capabilities
need. Read it when setting up a machine or when a capability reports a missing
dependency.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Installing the binary

Outside the [Brewfile](../../../Brewfile). Run [`./setup.sh`](../../setup.sh) —
an idempotent installer that clones the agent via `ghq` (only if missing), runs
upstream `setup-hermes.sh --runtime-only --test-environment` (Hermes' package
manager, PM, installs the pinned uv, Python and tools, the hash-verified `all`
dependency generation and the checkout's test interpreter), syncs the `EXTRAS`
capability set into that same generation, and publishes the checkout's
launchers into `~/.local/bin`. It makes no shell-rc edits and runs no
interactive wizard. Trim `EXTRAS` at the top of `setup.sh` for a leaner
environment.

```sh
~/.config/hermes/setup.sh     # install (safe to re-run)
hermes --version              # verify
hermes-python --print         # Hermes' own interpreter
```

Requires `ghq` (from `./install.sh --deps`).

- **`setup.sh` installs only the binary.** Run
  [`install.sh`](../../../install.sh) separately for the `~/.hermes/` symlinks,
  and store keys with `secret set …` (no `.env`).
- **Update with `hermes update`, not `setup.sh`.**
- **Never hardcode a Python path.** PM owns the interpreter and the dependency
  generation; there is no in-tree `venv/`. Helpers that need Hermes'
  dependencies run through [`hermes-python`](../../../bin/hermes-python)
  (`hermes-python <script.py>`, `hermes-python -m <module>`; `--test` selects
  the checkout's test interpreter, `HERMES_AGENT_DIR` overrides the checkout).
- **The full upstream installer is deliberately avoided:** it edits shell rc
  files (`~/.zshrc` is a symlink into this repo), seeds bundled skills and runs
  interactive stages.

## Secrets mechanics

What each Keychain layer holds, how the multiplex gateway filters them per
profile and why the helper gets one shot are in
[`../models-auth.md`](../models-auth.md) "Secrets layering"; the maintainer
rules for editing the helper are in [`../../AGENTS.md`](../../AGENTS.md)
"Secrets, auth and accounts".

- **No `.env` files.** Keys live in the macOS Keychain; the
  [`bin/hermes`](../../../bin/secret-shim) secret-shim injects the `global` and
  `hermes` layers at launch (`secret env -p global`, then `-p hermes`) for every
  `hermes` invocation, including every profile alias.
- **The shim does not isolate profiles.** Isolation happens in the multiplex
  gateway: each served profile's `secrets.command` runs
  `scripts/profile-secrets.sh <profile>`, because multiplex secret scopes never
  read the process env.
- **Store a key with `secret set NAME -p <layer>`.** The value is read from a
  no-echo prompt, never argv. CLI:
  [`secret`](../../../zsh/functions/secret.md).
- **Rotating an API key needs a gateway restart:** resident sessions inherit
  the environment injected at gateway launch.

## Web dashboard (tailnet)

`hermes dashboard` runs a full web UI (config, API keys, sessions, and a Chat
terminal). tmux `prefix H` lazily starts one shared, machine-level dashboard in
a detached `hermes-dashboard` session that survives closing every directory's
TUI, so mobile devices on the tailnet can reach it anytime. See
[`tmux/README.md`](../../../tmux/README.md#hermes-web-dashboard) for the binding
and launch mechanics.

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

**System packages** (declared in the [Brewfile](../../../Brewfile)): `ffmpeg`
(TTS / voice audio conversion), `portaudio` (CLI voice mode mic + playback),
`opus` (Discord voice-channel codec).

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
secret set EXA_API_KEY        -p global   # web search (see web-search.md)
secret set PARALLEL_API_KEY   -p global
secret set FIRECRAWL_API_KEY  -p global
```

Other optional keys: `FAL_KEY` (image/video generation fallback, paid SFX/music;
resolved through the scoped Keychain helper — no `.env`, provider-key terminal
passthrough or ElevenLabs subscription setup is needed for SFX),
`ELEVENLABS_API_KEY` (premium TTS / Scribe STT), `XAI_API_KEY` (x_search /
video_gen), `BROWSERBASE_API_KEY` (cloud browser). Bot tokens go in the per-bot
layers (see "Secrets mechanics" above). The web-search backends are in
[`web-search.md`](./web-search.md).
