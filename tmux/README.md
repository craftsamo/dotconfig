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
| `prefix o`                 | opencode popup — one detached session per directory, launched via `bin/opencode` (secret-shim) |
| `prefix H` (Shift+h)       | hermes popup — one detached session per directory, launched via `bin/hermes` (secret-shim) |
