# dotfiles

XDG-first dotfiles — this repository **is** `~/.config`. Most tools read
their config from here natively; the rest get symlinks created by
[`install.sh`](./install.sh). Secrets and runtime state never enter the repo.

## Managed configurations

| Tool                       | Config in repo | Wiring                                                                  |
| -------------------------- | -------------- | ----------------------------------------------------------------------- |
| [Neovim](./nvim/README.md) | `nvim/`        | XDG native                                                               |
| [Zsh](./zsh/README.md)     | `zsh/`         | XDG native + `~/.zshrc -> zsh/config.zsh` symlink                        |
| [Tmux](./tmux/README.md)   | `tmux/`        | XDG native (tmux >= 3.1)                                                 |
| Ghostty                    | `ghostty/`     | XDG native                                                               |
| lazygit                    | `lazygit/`     | XDG native                                                               |
| mise                       | `mise/`        | XDG native; declares language runtimes + global npm CLIs                 |
| [opencode](./opencode/README.md) | `opencode/` | XDG native                                                            |
| Git                        | `git/`         | XDG fallback (`~/.gitconfig` must not exist); `git/credentials` ignored  |
| [Claude Code](./claude/README.md) | `claude/` | 6 symlinks in `~/.claude/`                                             |
| [Codex](./codex/README.md) | `codex/`       | 3 symlinks in `~/.codex/` (`skills/.system` and `config.toml` are app-managed, git-ignored) |
| [Gemini CLI](./gemini/README.md) | `gemini/`  | 3 symlinks in `~/.gemini/`                                              |
| [GitHub Copilot](./copilot/README.md) | `copilot/` | 4 symlinks in `~/.copilot/` (`config.json` is app-managed; auth dir `github-copilot/` git-ignored) |

State and secrets (`~/.codex/auth.json`, sqlite logs, `~/.claude/history.jsonl`,
transcripts, ...) stay in the tool directories and are never tracked.
Development secrets (API keys, tokens) live in the macOS Keychain, managed
from the terminal by [`secret`](./zsh/functions/secret.md) — per-project
keychains, one master password, encrypted export/import. The
[`bin/secret-shim`](./bin/secret-shim) launchers inject them into the AI
CLIs (opencode, Claude Code, Codex, Copilot) and dev runtimes (npm, pnpm,
node, python, ...) at startup — no `.env` files needed, and existing `.env`
files keep priority.

## Fresh machine setup

```sh
# 1. Clone as ~/.config (back up / merge any existing ~/.config first)
git clone git@github.com:craftsamo/dotfiles.git ~/.config

# 2. Install dependencies (Homebrew bootstrap + brew bundle) and create symlinks
~/.config/install.sh --deps

# 3. Restart the shell
exec zsh
```

Installed outside the [Brewfile](./Brewfile):

- **Claude Code CLI** — [native installer](https://claude.com/product/claude-code)
  (lands in `~/.local/bin/claude`)
- **Language runtimes** (Node.js, Python, Ruby, Rust, Bun) and global npm
  CLIs — declared in [`mise/config.toml`](./mise/config.toml);
  `install.sh --deps` runs `mise install` after `brew bundle`

## install.sh

```sh
./install.sh          # symlinks only — idempotent, offline, safe to re-run
./install.sh --deps   # + Homebrew bootstrap (if missing) + brew bundle
```

- Never overwrites a real file: if a tool replaced a symlink with a regular
  file it prints `WARN` and skips, so re-running it doubles as a drift check.
- `brew bundle` runs with `HOMEBREW_BUNDLE_NO_UPGRADE=1` (installs what is
  missing, upgrades nothing) and `HOMEBREW_CASK_OPTS=--adopt` (takes ownership
  of manually installed apps instead of failing).
- If adopting an app requires elevated permissions (e.g. it is owned by
  `root`, like a Claude.app installed for all users), run
  `brew install --cask --adopt <name>` once in an interactive terminal so
  sudo can prompt for a password.

## Homebrew

Currently installed per-user at `~/.homebrew` (no sudo required). Everything
is prefix-agnostic: `install.sh` and `zsh/config.zsh` pick up `brew` from
`PATH`, `/opt/homebrew`, or `~/.homebrew`, in that order.

### Migrating to a global /opt/homebrew (planned)

A single shared install avoids per-user duplication on multi-user machines.
Homebrew does not officially support multi-user usage: run installs/upgrades
from one admin account only; other accounts just consume.

```sh
# 1. Official installer (requires sudo)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Reinstall the curated packages into the new prefix
eval "$(/opt/homebrew/bin/brew shellenv)"
brew bundle --file=~/.config/Brewfile

# 3. New shells pick /opt/homebrew automatically (zsh/config.zsh prefers it).
#    After verifying tools resolve to /opt/homebrew/bin:
rm -rf ~/.homebrew
```

## Adding a new managed config

1. Put the real file under `<tool>/` in this repo (never the secrets).
2. If the tool does not read `~/.config` natively, add a `link` line to
   `install.sh`.
3. Run `./install.sh`, verify, commit.
