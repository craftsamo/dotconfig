# Hermes Agent

Hermes is the self-improving agent CLI by Nous Research. This directory holds
its version-controlled configuration: several cooperating profiles (assistant,
marketer, creator, writer, researcher, searcher and the three media hands), the
plugins they use and the scripts that run them. Start here to find the right
document; this file keeps only what every reader needs.

Hermes keeps everything under `~/.hermes/` and does **not** read `~/.config`, so
[`install.sh`](../install.sh) links the files in this directory into place
("Symlinks" below).
Hermes never loads this file, [`AGENTS.md`](./AGENTS.md) or `docs/` at runtime:
a profile sees only its `config.yaml`, `SOUL.md` and skills.

## Where to look

| I want to ...                                                | Read                                                                                                           |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| change something safely (what must not break, and why)       | [`AGENTS.md`](./AGENTS.md) — maintainer rules, one-line why each                                               |
| understand how the agents fit together and what each does    | [`PROFILES.md`](./PROFILES.md) — index of the design docs in [`docs/`](./docs/)                                |
| install, link, track a profile, move files                   | [`docs/ops/install.md`](docs/ops/install.md), [`docs/ops/tracking.md`](docs/ops/tracking.md)                   |
| add or change a scheduled (cron) job                         | [`docs/ops/cron.md`](docs/ops/cron.md)                                                                         |
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
~/ghq/github.com/craftsamo/dotconfig/install.sh   # the ~/.hermes/ links (re-run after adding files)
hermes --version               # verify
```

Keys live in the macOS Keychain (`secret set …`), never in a `.env`. Update
with `hermes update`, not `setup.sh`. Details and the reasons:
[`docs/ops/install.md`](docs/ops/install.md).

## Runtime dependency: local patches

This configuration targets a **patched** Hermes, not stock upstream. The
runtime is the `local` branch of a hermes-agent checkout (remote `fork`): a
pinned upstream snapshot plus every local `fix/*` and `feat/*` branch, merged.
`setup.sh` clones stock upstream only, so on a fresh machine add the `fork`
remote and check out `local` before relying on this repo. Without the patches
the configs still load, but some parts fail silently or not at all:

- thinking and `tool_choice` handling for newer Claude models
  ([`docs/models-auth.md`](docs/models-auth.md) "Fable and the Claude weekly pool");
- real-profile browser isolation ([`docs/ops/browser.md`](docs/ops/browser.md));
- scope-keyed audio handling ([`docs/hands/audio.md`](docs/hands/audio.md));
- room for a plugin's approval card past the 500-unit reason cut, without
  which a long card (a stack merge with several layers) is refused
  ([`docs/access-common.md`](docs/access-common.md) "Card shape").

The base is a `pin/main-<date>` branch: upstream `main` fixed at one commit,
the first parent at the root of `local`. `origin/main` moves on past it and is
not what runs. The branches are kept this way:

- **A new patch** branches from the current pin, never from `local` or
  `origin/main`, so it rebases onto the next pin alone; it is merged into
  `local` with a merge commit (`Merge fix/<name> into local`).
- **Re-pinning** (taking newer upstream) creates the new `pin/main-<date>`,
  rebases every `fix/*` / `feat/*` branch onto it, rebuilds `local` on a
  scratch branch by merging them in again, and only then resets `local` to the
  result. A patch upstream now carries is archived under `archive/<date>/…`
  instead of merged. A rebuilt `local` needs a force push to `fork/local`.

`local` is what the gateway runs, so it moves only by these two steps: a
finished patch merged in, or a re-pin's reset to an already rebuilt result.

The branch list in the checkout is the ledger, not a list in these docs:
`./scripts/check-local-patches.sh` fails on any `fix/*` / `feat/*` branch that
`local` does not contain. Run it after every `hermes update`
([`AGENTS.md`](./AGENTS.md) "After `hermes update`").

## Symlinks

`~/.hermes/` and every profile home are real, machine-local directories:
Hermes' runtime state (auth, sessions, memories, cron, learned skills) lives
there, beside links into this repo. Links point from HOME into the repo, never
the other way, and nothing inside this tree is a link — so edit the repo copy,
and nothing Hermes writes lands here. `install.sh`'s `link()` never overwrites
a real file: it prints `WARN … not overwriting` and skips.

| `~/.hermes/…`                    | Wired as                                                                                      |
| -------------------------------- | --------------------------------------------------------------------------------------------- |
| `config.yaml`, `SOUL.md`         | link to the private overlay; seeded from the examples without it                              |
| `mcp.json`, `.no-bundled-skills` | link to `hermes/<file>`                                                                       |
| `skills/`                        | real dir: `pipeline` → `hermes/skills/pipeline`; `learned/` and Hermes' bookkeeping beside it |
| `plugins/<group>/`               | real dirs: each `<name>` → `hermes/plugins/<group>/<name>`; the overlay's plugins beside them |

For every `hermes/profiles/<name>/`, `install.sh` wires the same pieces into
`~/.hermes/profiles/<name>/`: `config.yaml` and `SOUL.md` as above;
`profile.yaml`, `mcp.json` and `.no-bundled-skills` as links; `skills/` as a
real directory holding `pipeline` and `technic` links (learned skills
land beside them); `cron.d/` as a real directory holding one link per tracked
job directory (the overlay's and the profile's own jobs beside them; the
installer's last step derives `cron/jobs.json` from the whole set,
[`docs/ops/cron.md`](docs/ops/cron.md)); `scripts/` as a real directory of
**copies** (Hermes' cron scheduler resolves a script and the directory to
their real paths and refuses a script outside the directory, so a link cannot
serve; the repo is the source, re-run `install.sh` after editing); and
`plugins` as a link to the one `~/.hermes/plugins` tree (plugin discovery is
`HERMES_HOME`-scoped). It never links `cron/`.

The private overlay (the sibling `private-dotconfig` checkout), when present,
runs its own `install.sh` last and links the real `config.yaml` and `SOUL.md`
of every profile, and its plugins, straight into `~/.hermes`. A seed the
public installer left untouched yields to that link; an edited one is kept and
warned about.

## Layout

```
config.example.yaml    default profile: models, providers, toolsets; the real config.yaml
                       is private and untracked (Hermes rewrites it)
mcp.json               MCP servers ({} = none)
SOUL.example.md        persona template; the real SOUL.md is private and untracked
setup.sh               installs the binary only
skills/                pipeline/ (shared) and learned/ (runtime-authored, ignored)
plugins/               grouped plugins: messaging/ social/ web3/ orchestration/ workspace/
                       guards/ inspection/ and the media families (image_gen/ video_gen/
                       audio_gen/ tts/ transcription/); _shared/ dirs are code, not plugins
profiles/<name>/       one HERMES_HOME each: config.example.yaml, profile.yaml, SOUL.example.md,
                       skills/pipeline/, scripts/ (see docs/ops/skills.md), cron.d/<job>/
                       (tracked cron jobs, see docs/ops/cron.md)
launchd/               LaunchAgent templates and launcher scripts
engines/               hash-locked pins for the local engines (TTS, SFX, scraping, ...) and
                       the screen-listen helper's Swift source
scripts/               helpers, validators and tests/ (see "Commands")
docs/                  design contracts (index: PROFILES.md) and docs/ops/ mechanics
archive/               retired material no profile reads
                       (machine-local installs — engine venvs, weights, the browser clone —
                       live outside the repository at ~/.hermes/local/; HERMES_LOCAL overrides)
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
  names what is missing ([Runtime dependency: local patches](#runtime-dependency-local-patches)).
- `hermes doctor` — validate providers and model tiers.
- `../bin/hermes-python scripts/cron-sync.py [--check]` — derive every
  profile's `cron/jobs.json` from its `cron.d/` links (`install.sh` runs it
  last); `--check` reports pending changes and writes nothing
  ([`docs/ops/cron.md`](docs/ops/cron.md)).

**Validation and tests**

- `./scripts/validate-profile-skills.py --all` — skill topology, metadata,
  routing registries, hands leaves, references and Git ownership. `--strict-git`
  in a staged or clean tree also fails on managed files that are untracked.
- `hermes-python --test scripts/audit-hands-references.py --root .. --json`
  (or `--leaf <repo-relative leaf dir>` for one leaf; needs PyYAML) — the
  option-backed reference catalogs of the image, video and audio hands: orphan
  files, empty backing, missing loading links, and the card renderer's
  destination and style contracts. Exit 0 is structural only; findings still
  need reading.
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
