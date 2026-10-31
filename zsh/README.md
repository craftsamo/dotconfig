# Zsh

`env.zsh` (every shell) and `config.zsh` (interactive) are the entry points.
[`install.sh`](../install.sh) wires them up as symlinks:
`~/.zshenv -> ~/.config/zsh/env.zsh` and
`~/.zshrc -> ~/.config/zsh/config.zsh`.

```sh
~/.config/install.sh   # creates the symlink (idempotent)
exec zsh
```

## Load order

`env.zsh` runs for _every_ zsh — including non-interactive `zsh -c`
(opencode's bash tool, tmux launchers, scripts). It builds `PATH`:
`~/.config/bin` (secret-shim launchers — see
[secret.md](./functions/secret.md)), `~/.local/bin`, `~/bin`, Docker,
mise shims (node / pnpm / ...), then the Homebrew prefix. It also exports
mise's directories (`MISE_DATA_DIR`, `MISE_CONFIG_DIR`, `MISE_STATE_DIR`,
`MISE_CACHE_DIR`) as absolute paths, keeping an inherited value. A child
that swaps `HOME` for a temp dir but keeps `PATH` would otherwise run the
shims against an empty data dir, while still finding
`~/.config/mise/config.toml` through its cwd: mise then sees no installed
tool and resolves, and installs, every `latest` tool from the network on
each shim call (before mise 2026.10.5, `npm view` re-entering the shims
made that a process explosion). The pins equal mise's defaults with the
`XDG_*` base dirs unset; a child that wants a clean mise sets (or unsets)
`MISE_*` along with `HOME`.

`config.zsh` adds the interactive layer on top:

1. Aliases (`ls` / `la` / `ll` / `lla`, `g` = git, `vim` -> nvim) and
   `EDITOR=nvim`
2. Homebrew `shellenv` — prefix-agnostic: prefers `~/.homebrew`, falls back
   to `/opt/homebrew`
3. `mise activate` — language runtimes declared in `mise/config.toml`; its
   per-directory tool paths take precedence over the shims from `env.zsh`
4. Sources `conf.d/*.zsh`, then `functions/*.zsh`, then `*.zsh` in this
   directory (everything except `config.zsh` itself; re-sourcing `env.zsh`
   here is idempotent)

## Files

| File                                                         | Purpose                                                                                                                        |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `conf.d/cursor.zsh`                                          | keeps the bar cursor after TUIs (nvim, less, ...) reset it                                                                     |
| `conf.d/tide.zsh`                                            | colours for the fish-era tide prompt — inert under zsh, kept for reference                                                     |
| `functions/zsh_user_key_bindings.zsh`                        | emacs keymap, `Ctrl-F` fzf directory jump, `Ctrl-D` delete-char                                                                |
| `functions/fzf_change_directory.zsh`                         | fzf picker over `~/.config`, the Workspaces root (every area's groups + grouped repos, from `ws-layout`), ghq repos, and `./*` |
| `functions/secret.zsh`                                       | macOS Keychain secrets CLI + fzf wizard — see [secret.md](./functions/secret.md)                                               |
| `tests/secret-selftest.zsh`                                  | self-test for `secret` (not auto-sourced); `zsh -f zsh/tests/secret-selftest.zsh`                                              |
| `tests/secret-shim-selftest.zsh`                             | self-test for the `bin/secret-shim` launchers; `zsh -f zsh/tests/secret-shim-selftest.zsh`                                     |
| `config-osx.zsh` / `config-linux.zsh` / `config-windows.zsh` | fish-era OS snippets; sourced on every OS, mostly commented out / inert                                                        |

## Customisation

Add aliases to `config.zsh`, or drop a new `*.zsh` file into `conf.d/` — it is
picked up automatically on the next shell start.
