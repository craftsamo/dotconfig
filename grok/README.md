# Grok Build

User-level configuration for [Grok Build](https://docs.x.ai/build/overview),
xAI's `grok` CLI coding agent.
[`install.sh`](../install.sh) symlinks `AGENTS.md` and seeds `config.toml`
into `~/.grok/`:

| `~/.grok/` file | Repo source        | How                                   |
| --------------- | ------------------ | ------------------------------------- |
| `AGENTS.md`     | `grok/AGENTS.md`   | symlink                               |
| `config.toml`   | `grok/config.toml` | seeded on first install (not symlinked) |

`config.toml` is seeded rather than symlinked because the CLI atomically
rewrites the live file on every run (temp file + rename), which would replace
a symlink with a real file each launch — the same reason codex's config is
app-managed. The repo copy is the baseline a fresh machine starts from; edit
it to change that baseline. The CLI owns `~/.grok/config.toml` afterwards, so
re-running `install.sh` never clobbers it.

## Install / update

NOT installed via Homebrew: binaries under `/opt/homebrew/Caskroom` hang in
dyld on this machine (the `grok-build` cask binary never starts; the same
binary runs fine from any other path). Like Claude Code CLI, it uses the
official installer instead:

```sh
SHELL=/bin/sh bash -c "$(curl -fsSL https://x.ai/cli/install.sh)"
```

`SHELL=/bin/sh` stops the installer from appending a PATH block to the
version-managed `~/.zshrc`. It is not needed anyway: the installer symlinks
`grok` and `agent` into `~/.local/bin`, which is already on `PATH`. Updates go
through `grok update` (or the CLI's own auto-updater).

## User-managed content

- `config.toml` — baseline seeded on first install; the live `~/.grok/config.toml`
  is CLI-owned (see the seeding note above)
- `AGENTS.md` — global rules, loaded into every session
- `skills/<name>/SKILL.md` — grok-specific user skills, discovered via
  `[skills] paths`. Claude-compat scanning is left on, so the skills tracked
  under [`claude/skills/`](../claude/skills) are shared with grok for free.

## Secrets

`~/.config/bin/grok` routes launches through `secret-shim` (tool mode:
Keychain layers `global` → `grok`). Interactive auth is `grok login` (browser
OAuth; token in `~/.grok/auth.json`, never in the repo). For headless/CI use,
add an API key with `secret set XAI_API_KEY -p grok` — the shim injects it
only into grok's process.

## Intentionally untracked

Everything else in `~/.grok/` is tool state and stays out of the repo:
`auth.json`, `sessions/`, `logs/`, `memory/`, `bin/`, `downloads/`,
`completions/`, `skills/` (bundled skills auto-expand there),
`trusted_folders.toml`, `active_sessions.*`.
