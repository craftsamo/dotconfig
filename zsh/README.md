# Zsh

`config.zsh` is the entry point. [`install.sh`](../install.sh) wires it up as
a symlink: `~/.zshrc -> ~/.config/zsh/config.zsh`.

```sh
~/.config/install.sh   # creates the symlink (idempotent)
exec zsh
```

## Load order

`config.zsh` sets the basics, then sources everything else:

1. Aliases (`ls` / `la` / `ll` / `lla`, `g` = git, `vim` -> nvim) and
   `EDITOR=nvim`
2. Homebrew `shellenv` — prefix-agnostic: prefers `/opt/homebrew`, falls back
   to `~/.homebrew`
3. `mise activate` — language runtimes declared in `mise/config.toml`
4. `PATH` additions: `~/.config/bin` (secret-shim launchers — see
   [secret.md](./functions/secret.md)), `~/.local/bin`, Docker
5. Sources `conf.d/*.zsh`, then `functions/*.zsh`, then `*.zsh` in this
   directory (everything except `config.zsh` itself)

## Files

| File                                  | Purpose                                                                    |
| ------------------------------------- | -------------------------------------------------------------------------- |
| `conf.d/cursor.zsh`                   | keeps the bar cursor after TUIs (nvim, less, ...) reset it                 |
| `conf.d/tide.zsh`                     | colours for the fish-era tide prompt — inert under zsh, kept for reference |
| `functions/zsh_user_key_bindings.zsh` | emacs keymap, `Ctrl-F` fzf directory jump, `Ctrl-D` delete-char            |
| `functions/fzf_change_directory.zsh`  | fzf picker over `~/.config`, ghq repos, `./*` and `~/Github`               |
| `functions/secret.zsh`                | macOS Keychain secrets CLI + fzf wizard — see [secret.md](./functions/secret.md) |
| `tests/secret-selftest.zsh`           | self-test for `secret` (not auto-sourced); `zsh -f zsh/tests/secret-selftest.zsh` |
| `tests/secret-shim-selftest.zsh`      | self-test for the `bin/secret-shim` launchers; `zsh -f zsh/tests/secret-shim-selftest.zsh` |
| `config-osx.zsh` / `config-linux.zsh` / `config-windows.zsh` | fish-era OS snippets; sourced on every OS, mostly commented out / inert |

## Customisation

Add aliases to `config.zsh`, or drop a new `*.zsh` file into `conf.d/` — it is
picked up automatically on the next shell start.
