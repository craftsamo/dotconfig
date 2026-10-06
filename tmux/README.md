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

| Binding                  | Action                                                                                                                                                                              |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prefix r`               | reload `tmux.conf`                                                                                                                                                                  |
| `prefix h/j/k/l`         | switch pane (repeatable)                                                                                                                                                            |
| `prefix C-h/C-j/C-k/C-l` | resize pane by 5 cells (repeatable)                                                                                                                                                 |
| `Ctrl-Shift-Left/Right`  | move the current window left / right (no prefix)                                                                                                                                    |
| `prefix e`               | kill every pane except the current one                                                                                                                                              |
| `prefix f`               | open the pane's directory in Finder                                                                                                                                                 |
| `prefix g`               | lazygit popup (80% x 80%)                                                                                                                                                           |
| `prefix o`               | opencode popup — one detached TUI session per directory, connected to OpenCode's shared background service                                                                          |
| `prefix O` (Shift+o)     | reload OpenCode configuration for every loaded project after confirmation                                                                                                           |
| `prefix H` (Shift+h)     | hermes popup (modern TUI) — one detached session per directory, launched via `bin/hermes --tui` (secret-shim); also starts the shared, tailnet-only web dashboard in the background |

## OpenCode

OpenCode 2 runs one shared background service per user (`127.0.0.1:49374`).
The first `opencode` client starts it, it survives closing every TUI, and
every directory's TUI talks to it. `prefix o` only keeps one detached tmux
session per directory running `opencode <path>` through the secret shim;
there is no server of its own to start. Existing directory sessions are not
replaced while they are running.

The service inherits the environment of the client that started it, so
Keychain secrets come from the shim at that moment. After changing a secret,
restart it with `opencode service restart`, which also runs through the shim.

`prefix O` runs `opencode reload`: the service rebuilds configuration for
every project it has loaded, not just the pane's. Pending permission prompts
and questions are cancelled; running sessions pick up the new configuration at
their next step. Configuration and plugin files are also watched and reloaded
on change, so `prefix O` is mostly for changes outside those files.

Web and mobile access, the service's password and Tailscale Serve:
[`opencode/README.md`](../opencode/README.md#web-access).

## Hermes web dashboard

The first `prefix H` also starts the shared Hermes web dashboard in a detached
`hermes-dashboard` tmux session (background, non-blocking). It survives closing
every directory's Hermes TUI, so mobile devices on the tailnet can reach it at
any time. Later `prefix H` presses reuse the running dashboard instead of
starting another.

The dashboard binds to this machine's **Tailscale IPv4 only** (`--host <ip>`,
port `9119`) — never `0.0.0.0` or the LAN. Tailscale encrypts the transport,
and a username/password gate (Hermes' bundled Basic provider) protects the
sensitive routes; `/api/status` remains public as a liveness probe. Credentials
come from the Keychain via the `hermes` secret layer
(`HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` / `_SECRET`); `dashboard.basic_auth.username`
in `hermes/config.yaml` holds the non-secret username. Provision the two
Keychain values once on a new machine using the commands in
[`hermes/README.md`](../hermes/README.md#web-dashboard-tailnet); the browser then
stays signed in across restarts.

Open the dashboard from any tailnet device:

```sh
tailscale ip -4                                   # this machine's tailnet IPv4
# browse:  http://<tailnet-ip>:9119
```

Verify the gate from any machine (`/api/status` is public even under auth):

```sh
curl -s http://<tailnet-ip>:9119/api/status | jq '.auth_required, .auth_providers'
# true
# ["basic"]
```

Notes:

- The dashboard's web Chat spins up its **own** TUI process scoped to the
  selected profile — it does not mirror a directory's live TUI. It shares the
  same profile and saved sessions, so it is a parallel entry point, not a
  continuation of an in-progress terminal conversation.
- A first launch builds the web UI (npm) and can take a while before the server
  responds; later launches are fast. The startup log is
  `~/Library/Logs/hermes-dashboard.log`.
- A session bound to an old Tailscale address is replaced automatically. An
  unresponsive session on the expected address is preserved to avoid
  interrupting active web chats; a failed fresh warm-up is removed so the next
  `prefix H` can retry cleanly.
- Rotate the password without putting the value in history:

  ```sh
  secret set HERMES_DASHBOARD_BASIC_AUTH_PASSWORD -p hermes
  tmux kill-session -t hermes-dashboard   # next prefix H restarts it
  ```
