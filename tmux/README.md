# tmux

XDG native: tmux (>= 3.1) reads `~/.config/tmux/tmux.conf` directly — no
symlink or setup step needed.

## Files

| File              | Purpose                                                          |
| ----------------- | ---------------------------------------------------------------- |
| `tmux.conf`       | core options and key bindings; sources the files below           |
| `statusline.conf` | status bar and pane colours — Neon Dark palette, matches Ghostty |
| `utility.conf`    | popup helpers: lazygit, opencode, and hermes                     |
| `macos.conf`      | Darwin only: clipboard (reattach-to-user-namespace), undercurl   |

## Behaviour

- Prefix is `C-t` (`C-b` is unbound)
- vi copy-mode, bar cursor, 24-bit colour + undercurl, focus events,
  64k scrollback, 10ms escape time
- Mouse is on: wheel scroll (enters copy-mode), pane select, and resize by drag
- Inactive panes are slightly dimmed; the active pane border is neon green

## Key bindings

| Binding                    | Action                                          |
| -------------------------- | ----------------------------------------------- |
| `prefix r`                 | reload `tmux.conf`                              |
| `prefix h/j/k/l`           | switch pane (repeatable)                        |
| `prefix C-h/C-j/C-k/C-l`   | resize pane by 5 cells (repeatable)             |
| `Ctrl-Shift-Left/Right`    | move the current window left / right (no prefix) |
| `prefix e`                 | kill every pane except the current one          |
| `prefix f`                 | open the pane's directory in Finder             |
| `prefix g`                 | lazygit popup (80% x 80%)                       |
| `prefix o`                 | opencode popup — starts the shared web server if needed, then opens one detached TUI session per directory |
| `prefix H` (Shift+h)       | hermes popup (modern TUI) — one detached session per directory, launched via `bin/hermes --tui` (secret-shim) |

## OpenCode web server

The first `prefix o` starts `opencode serve` in the detached `opencode-web`
session. The server listens only on `127.0.0.1:4096`; the existing TUI remains
one independent process per directory. A startup failure does not block the
TUI; tmux displays the path to the persistent
`~/Library/Logs/opencode-web.log` startup log.

`OPENCODE_SERVER_PASSWORD` must exist in the `opencode` Keychain layer. Add or
replace it interactively without putting the value in shell history:

```sh
secret set OPENCODE_SERVER_PASSWORD -p opencode
```

After replacing the password, restart the server so the old credential stops
working. The next `prefix o` starts it again with the new value:

```sh
tmux kill-session -t opencode-web
```

The web server is intended to be exposed to the tailnet with Tailscale Serve,
not by binding OpenCode to the LAN. Enable Serve for the tailnet when prompted,
then configure the persistent HTTPS proxy once:

```sh
tailscale serve --bg 127.0.0.1:4096
```

Check the local process and proxy with:

```sh
tmux has-session -t opencode-web
tailscale serve status
```
