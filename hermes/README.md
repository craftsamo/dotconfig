# Hermes Agent

Hermes is the self-improving agent CLI by Nous Research. This directory holds
its version-controlled configuration: several cooperating profiles (assistant,
marketer, creator, writer, researcher, searcher and the three media hands), the
plugins they use and the scripts that run them. Start here to find the right
document; this file keeps only what every reader needs.

Hermes keeps everything under `~/.hermes/` and does **not** read `~/.config`, so
[`install.sh`](../install.sh) symlinks the files in this directory into place.
Hermes never loads this file, [`AGENTS.md`](./AGENTS.md) or `docs/` at runtime:
a profile sees only its `config.yaml`, `SOUL.md` and skills.

## Where to look

| I want to ...                                                | Read                                                                                                           |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| change something safely (what must not break, and why)       | [`AGENTS.md`](./AGENTS.md) — maintainer rules, one-line why each                                               |
| understand how the agents fit together and what each does    | [`PROFILES.md`](./PROFILES.md) — index of the design docs in [`docs/`](./docs/)                                |
| install, link, track a profile, move files                   | [`docs/ops/install.md`](docs/ops/install.md), [`docs/ops/tracking.md`](docs/ops/tracking.md)                   |
| add or change skills; why a worker command is refused        | [`docs/ops/skills.md`](docs/ops/skills.md)                                                                     |
| enable or configure a plugin                                 | [`docs/ops/plugins.md`](docs/ops/plugins.md)                                                                   |
| run or repair a LaunchAgent, a launcher or an engine script  | [`docs/ops/services.md`](docs/ops/services.md)                                                                 |
| set up local text-to-speech, speech-to-text or audio tooling | [`docs/ops/tts-engines.md`](docs/ops/tts-engines.md), [`docs/ops/audio-tooling.md`](docs/ops/audio-tooling.md) |
| change web search or the browser                             | [`docs/ops/web-search.md`](docs/ops/web-search.md), [`docs/ops/browser.md`](docs/ops/browser.md)               |
| change models, authentication or secrets                     | [`docs/models-auth.md`](docs/models-auth.md)                                                                   |
| see why a decision was made                                  | [`docs/decisions/`](docs/decisions/)                                                                           |

## Install in short

```sh
~/.config/hermes/setup.sh      # the binary (idempotent; ghq + PM do the rest)
~/.config/install.sh           # the ~/.hermes/ symlinks (re-run after adding files)
hermes --version               # verify
```

Keys live in the macOS Keychain (`secret set …`), never in a `.env`. Update
with `hermes update`, not `setup.sh`. Details and the reasons:
[`docs/ops/install.md`](docs/ops/install.md).

## Symlinks

Every link below points back into this repo, so edit the repo copy.
`install.sh`'s `link()` never overwrites a real file: it prints
`WARN … not overwriting` and skips.

| Symlink                        | Target                                  |
| ------------------------------ | --------------------------------------- |
| `~/.hermes/config.yaml`        | `hermes/config.yaml`                    |
| `~/.hermes/SOUL.md`            | `hermes/SOUL.md` (untracked; see below) |
| `~/.hermes/mcp.json`           | `hermes/mcp.json`                       |
| `~/.hermes/skills`             | `hermes/skills/`                        |
| `~/.hermes/plugins`            | `hermes/plugins/`                       |
| `~/.hermes/.no-bundled-skills` | `hermes/.no-bundled-skills`             |

For every `hermes/profiles/<name>/`, `install.sh` links `config.yaml`,
`profile.yaml`, `SOUL.md`, `mcp.json`, `scripts/`, `skills/` and
`.no-bundled-skills` (when present) into `~/.hermes/profiles/<name>/`, plus the
shared `hermes/plugins/` (plugin discovery is `HERMES_HOME`-scoped). It never
links `cron/`.

A missing `SOUL.md` is seeded from the tracked `SOUL.example.md`, and the
assistant's missing `config.yaml` from `config.example.yaml`; seeded copies stay
untracked. The private overlay (`~/.config/private`, the `private-dotconfig`
repo), when present, runs its own `install.sh` last and overlays the real
`SOUL.md` files and `profiles/assistant/config.yaml`.

## Layout

```
config.yaml            default profile: models, providers, toolsets (Hermes rewrites it)
mcp.json               MCP servers ({} = none)
SOUL.example.md        persona template; the real SOUL.md is private and untracked
setup.sh               installs the binary only
skills/                default-pipeline/ (shared) and learned/ (runtime-authored, ignored)
plugins/               grouped plugins: messaging/ social/ web3/ orchestration/ workspace/
                       guards/ inspection/ and the media families (image_gen/ video_gen/
                       audio_gen/ tts/ transcription/); _shared/ dirs are code, not plugins
profiles/<name>/       one HERMES_HOME each: config.yaml, profile.yaml, SOUL.example.md,
                       skills/<name>-pipeline/, scripts/ (see docs/ops/skills.md)
launchd/               LaunchAgent templates and launcher scripts
engines/               hash-locked pins for the local engines (TTS, SFX, scraping, ...)
scripts/               helpers, validators and tests/ (see "Commands")
docs/                  design contracts (index: PROFILES.md) and docs/ops/ mechanics
archive/               retired material no profile reads
local/                 machine-local installs: engine venvs, weights, the browser clone
                       (ignored)
```

What is tracked and what is ignored, and who owns each kind of skill:
[`docs/ops/tracking.md`](docs/ops/tracking.md) "Tracked vs ignored". Skill
placement rules: [`docs/ops/skills.md`](docs/ops/skills.md) "Skill placement".

## Commands

Run from `~/.config/hermes`.

**Setup and upkeep**

- `./setup.sh` — install or refresh the Hermes runtime; idempotent.
- `../install.sh` — create the `~/.hermes/` symlinks (after adding files).
- `hermes update` — update (not `setup.sh`), then follow the post-update steps in
  [`AGENTS.md`](./AGENTS.md) "After `hermes update`".
- `./scripts/check-local-patches.sh [hermes-agent-dir]` — every local `fix/*`
  branch of the hermes-agent checkout must still be merged into `local`; exit 1
  names what is missing.
- `hermes doctor` — validate providers and model tiers.

**Validation and tests**

- `./scripts/validate-profile-skills.py --all` — skill topology, metadata,
  routing registries, hands leaves, references and Git ownership. `--strict-git`
  in a staged or clean tree also fails on managed files that are untracked.
- Full test suite:

  ```sh
  cd ~/.config/hermes &&
    PYTHONPATH=$(ghq root)/github.com/NousResearch/hermes-agent \
    hermes-python --test -m pytest plugins/ scripts/tests/ -q --import-mode=importlib
  ```

  The Hermes test interpreter is required (plugins import `agent.*` / `tools.*`).
  `--import-mode=importlib` is not optional: every plugin keeps its suite at
  `tests/test_plugin.py`, those basenames collide under the default import mode,
  and the hyphenated plugin directories are not importable package names.
  In a task worktree, run `../worktree-setup.sh` once first: the private
  overlay links are gitignored, so without them the overlay-dependent tests
  skip (or are not collected) rather than run. Tests needing `numpy` or
  `fal_client`, which the test environment lacks, skip with that reason.

- `./scripts/verify-work-continuity.py --runtime <hermes-agent-checkout> --private <paired-private-checkout>`
  — before a cutover and after every upstream update; it installs, restarts and
  migrates nothing. What it proves and the paired-candidate rules:
  [`docs/ops/services.md`](docs/ops/services.md) "Work continuity and
  candidates".

**Services** (LaunchAgents, launchers, engine scripts):
[`docs/ops/services.md`](docs/ops/services.md).
