# dotconfig

XDG-first dotconfig. The repository is a ghq checkout
(`~/ghq/github.com/craftsamo/dotconfig`); [`install.sh`](./install.sh) links
each tracked top-level directory into `~/.config/<name>`, so XDG-native tools
read their config there, while tools that write their own state into
`~/.config` (gh, gcloud, ...) stay outside the repository. Tools that do not
read `~/.config` get symlinks in their own dirs. Secrets and runtime state
never enter the repo.

## Managed configurations

Every directory below is linked as `~/.config/<dir>`; "XDG native" means the
tool reads it from there without further wiring.

| Tool                                      | Config in repo | Wiring                                                                                                                                                                         |
| ----------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [Neovim](./nvim/README.md)                | `nvim/`        | XDG native                                                                                                                                                                     |
| [Zsh](./zsh/README.md)                    | `zsh/`         | XDG native + `~/.zshrc -> zsh/config.zsh` symlink                                                                                                                              |
| [Tmux](./tmux/README.md)                  | `tmux/`        | XDG native (tmux >= 3.1)                                                                                                                                                       |
| Ghostty                                   | `ghostty/`     | XDG native                                                                                                                                                                     |
| lazygit                                   | `lazygit/`     | XDG native                                                                                                                                                                     |
| mise                                      | `mise/`        | XDG native; declares language runtimes + global npm CLIs                                                                                                                       |
| [opencode](./opencode/README.md)          | `opencode/`    | XDG native; `~/.config/opencode` and its `skills/` are real dirs linked per entry (OpenCode and `hyperframes skills` write beside them); `cli.json` seeded, not linked         |
| Keychain shims                            | `bin/`         | `~/.config/bin` on PATH (see below)                                                                                                                                            |
| [Shared agent skills](./agents/README.md) | `agents/`      | not linked into `~/.config`; `agents/skills/` is linked per skill into the machine-local `~/.agents/skills` root (installer-writable), and each into `~/.claude/skills`        |
| Git                                       | `git/`         | XDG fallback (`~/.gitconfig` must not exist); `git/credentials` ignored                                                                                                        |
| [Claude Code](./claude/README.md)         | `claude/`      | 4 symlinks in `~/.claude/` plus per-skill links in `skills/` (`agents/` is machine-local, installer-written)                                                                   |
| [Codex](./codex/README.md)                | `codex/`       | 2 symlinks in `~/.codex/` (`skills/` and `config.toml` are machine-local, app/installer-managed)                                                                               |
| [Gemini CLI](./gemini/README.md)          | `gemini/`      | 3 symlinks in `~/.gemini/`                                                                                                                                                     |
| [GitHub Copilot](./copilot/README.md)     | `copilot/`     | 3 symlinks in `~/.copilot/` (`skills/` is machine-local; `config.json` is app-managed; auth dir `github-copilot/` git-ignored)                                                 |
| [Grok Build](./grok/README.md)            | `grok/`        | `AGENTS.md` symlinked, `config.toml` seeded (CLI-owned); state/auth stay in `~/.grok/`; installed via official installer, not brew                                             |
| [Hermes Agent](./hermes/README.md)        | `hermes/`      | `~/.hermes/` (+ per profile) are real dirs holding links per tracked entry (skill roots, plugin groups); `scripts/` copied; skills via `external_dirs`; keys via Keychain shim |

State and secrets (`~/.codex/auth.json`, sqlite logs, `~/.claude/history.jsonl`,
transcripts, ...) stay in the tool directories and are never tracked.
Development secrets (API keys, tokens) live in the macOS Keychain, managed
from the terminal by [`secret`](./zsh/functions/secret.md) — per-project
keychains, one master password, encrypted export/import. The
[`bin/secret-shim`](./bin/secret-shim) launchers inject them into the AI
CLIs (opencode, Claude Code, Codex, Copilot, Grok Build, Hermes) and dev runtimes (npm, pnpm,
node, python, ...) at startup — no `.env` files needed, and existing `.env`
files keep priority.

## Fresh machine setup

```sh
# 1. Clone into the ghq layout (install.sh links it into ~/.config; move any
#    existing ~/.config/<dir> that a tracked directory would replace out of
#    the way first — install.sh never overwrites a real directory)
git clone git@github.com:craftsamo/dotconfig.git ~/ghq/github.com/craftsamo/dotconfig

# 2. Install dependencies (Homebrew bootstrap + brew bundle) and create symlinks
~/ghq/github.com/craftsamo/dotconfig/install.sh --deps

# 3. Restart the shell
exec zsh
```

Installed outside the [Brewfile](./Brewfile):

- **Claude Code CLI** — [native installer](https://claude.com/product/claude-code)
  (lands in `~/.local/bin/claude`)
- **Grok Build CLI** — official installer
  (`SHELL=/bin/sh bash -c "$(curl -fsSL https://x.ai/cli/install.sh)"`; lands
  in `~/.grok/bin`, symlinked into `~/.local/bin`). The `grok-build` cask is avoided on purpose — Caskroom
  binaries hang in dyld on this machine; see [`grok/README.md`](./grok/README.md)
- **Hermes Agent** — run [`hermes/setup.sh`](./hermes/setup.sh) (idempotent:
  `ghq` clone + `uv` venv + `~/.local/bin/hermes` symlink; no shell-rc edits).
  Update later with `hermes update`
- **Language runtimes** (Node.js, Python, Ruby, Rust, Bun) and global npm
  CLIs — declared in [`mise/config.toml`](./mise/config.toml);
  `install.sh --deps` runs `mise install` after `brew bundle`
- **GitHub CLI extensions** — `gh` has no manifest of its own, so they are
  declared in the `GH_EXTENSIONS` array at the top of
  [`install.sh`](./install.sh) and installed after `brew bundle`. Currently
  `github/gh-stack` (native stacked PRs), which the OpenCode `git_stack` /
  `git_publish` tools and the `git-pullrequest` and
  `approach-github-projects` skills require

## install.sh

```sh
./install.sh          # symlinks only — idempotent, offline, safe to re-run
./install.sh --deps   # + Homebrew bootstrap (if missing), brew bundle,
                      #   gh extensions, mise install
```

- `[config]` links every tracked top-level directory of the repo as
  `~/.config/<name>`; the set comes from the Git index, so a new directory
  needs no line in the script. The declared exceptions keep one invariant
  — links point from HOME into the repo, and a tool writes beside a link,
  never through one: `CONFIG_UNLINKED` (`agents/`, which nothing reads at
  that path), `ENTRY_ROOTS` (`opencode/` and `opencode/skills/`, real
  directories holding one link per tracked entry, so OpenCode's own files and
  installer droppings land outside the repo) and `SEEDED` (`opencode/cli.json`,
  copied once because OpenCode rewrites it by rename). Nothing else in
  `~/.config` is touched.
- `[hermes]` wires `~/.hermes` the same way (it is not under `~/.config`):
  the skill roots and plugin groups are entry roots, a profile's `scripts/`
  is copied (cron resolves real paths), and `config.yaml` / `SOUL.md` are
  owned at HOME — the private overlay's, or a seed of the example. Details:
  [hermes/README.md "Symlinks"](./hermes/README.md#symlinks).
- Never overwrites a real file: if a tool replaced a symlink with a regular
  file it prints `WARN` and skips, so re-running it doubles as a drift check.
- Each `--deps` stage records its own failure and the next one still runs; the
  symlink phase always runs, and the failure surfaces in the exit code.
- `GH_EXTENSIONS` is installed idempotently — already-present extensions are
  skipped rather than re-installed (`gh extension install` errors on those).
- `brew bundle` runs with `HOMEBREW_BUNDLE_NO_UPGRADE=1` (installs what is
  missing, upgrades nothing) and `HOMEBREW_CASK_OPTS=--adopt` (takes ownership
  of manually installed apps instead of failing).
- If adopting an app requires elevated permissions (e.g. it is owned by
  `root`, like a Claude.app installed for all users), run
  `brew install --cask --adopt <name>` once in an interactive terminal so
  sudo can prompt for a password.
- At the end it runs the private overlay's `install.sh` when the sibling
  checkout exists (`PRIVATE_DOTCONFIG` overrides the path) — see below.

## worktree-setup.sh

A task worktree carries only tracked files. `./worktree-setup.sh`, run inside
one, gives it what tests need from the live checkout: every gitignored symlink
there that points into the private overlay (the few files it places inside
public plugin and lib directories), and `opencode/node_modules` as a link to
the live copy. `--private <dir>` links those to another private checkout (a
paired candidate) instead. It writes only inside the
worktree, refuses to run in the live checkout, and never overwrites a real
file. If the worktree changes `opencode/package.json`, replace the link with
`npm install --prefix opencode`.

## Private overlay

This repo is public. Its private counterpart is `craftsamo/private-dotconfig`,
whose tree mirrors this repo's top level (`hermes/`, `opencode/`, `zsh/`, ...).
It is a sibling ghq checkout at the fixed path
**`~/ghq/github.com/craftsamo/private-dotconfig`**: files that need an absolute
path at runtime (Hermes `skills.external_dirs`, `zsh/config.zsh`,
`bin/characters`) name that checkout directly, and its own `install.sh` links
its files from HOME (`~/.hermes`, `~/.config/opencode`, `~/Workspaces`) beside
the links this repo's installer makes — never through this tree (a plugin's
private data is read from `~/.hermes/plugin-data/<plugin>/`, the opencode
credit lanes from `~/.config/opencode/credit-lanes.json`). The one exception
is the Irodori lexicon, which the engine's `register-lexicon` keeps in the
`hermes/local/` runtime directory. A clone without access simply has no
overlay checkout, and everything else works.

What lives there: private Hermes skills (read in place via
`skills.external_dirs` as `~/ghq/github.com/craftsamo/private-dotconfig/hermes/skills`), the real
persona/config files this repo only ships `*.example.*` templates for (linked
into `~/.hermes` by the overlay's `install.sh`), the assistant's personal
procedures (plugin skills and the external private shelf; the assistant
pipeline and the public workspace engines live here), private Hermes plugins
(linked into `~/.hermes/plugins/<group>/`), the `~/Workspaces` AGENTS.md
doctrine (linked straight into place), private opencode skills, and private
shell config (`zsh/*.zsh`, sourced by `config.zsh` when present).

```sh
ghq get git@github.com:craftsamo/private-dotconfig.git
./install.sh   # runs the overlay's install.sh after its own
```

## Homebrew

Currently installed per-user at `~/.homebrew` (no sudo required). Everything
is prefix-agnostic: `install.sh` and `zsh/config.zsh` pick up `brew` from
`PATH`, `~/.homebrew`, or `/opt/homebrew`, in that order.

### Prefix priority (~/.homebrew preferred)

Both prefixes are supported and auto-detected by `zsh/env.zsh`,
`zsh/config.zsh`, and `install.sh` (`find_brew`). When both are installed on the
same machine, per-user `~/.homebrew` wins — no sudo, self-contained in `$HOME`,
and your curated brew always takes precedence; a machine with only
`/opt/homebrew` uses that instead.

To switch a machine to global `/opt/homebrew` (a single shared install, useful
on multi-user machines — run installs/upgrades from one admin account only),
install it with the official installer, reinstall the packages, then flip the
priority in the files above or remove `~/.homebrew`:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"
brew bundle --file=~/.config/Brewfile
```

## Adding a new managed config

1. Put the real file under `<tool>/` in this repo (never the secrets) and
   `git add` it — `install.sh` links the directory into `~/.config` once it
   is in the index. If `~/.config/<tool>` already exists as a real directory
   (the tool wrote it first), move its contents into the repo and remove it
   before linking.
2. If the tool does not read `~/.config` natively, add a `link` line to
   `install.sh`.
3. Run `./install.sh`, verify, commit.
