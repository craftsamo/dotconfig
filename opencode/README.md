# opencode

XDG native: opencode reads `~/.config/opencode/` directly — no symlinks
needed.

## User-managed content

| Path             | Purpose                                                  |
| ---------------- | -------------------------------------------------------- |
| `opencode.jsonc` | main configuration (models, permissions, MCP, ...)       |
| `tui.json`       | TUI preferences                                          |
| `AGENTS.md`      | global instructions, loaded into every session           |
| `agent/`         | custom agents / subagents (`*.md`)                       |
| `command/`       | custom slash commands (`*.md`)                           |
| `instructions/`  | extra instruction files referenced from `opencode.jsonc` |
| `plugins/`       | plugins (`*.ts`)                                         |
| `skills/`        | opencode-only skills (`<name>/SKILL.md`)                 |
| `tool/`          | custom tools (`*.ts`)                                    |

Empty directories carry a `.gitkeep` so the skeleton survives a fresh clone.

`skills/` holds only the skills that depend on opencode itself — its
subagents, custom tools, or the Plan/Build handoff. Skills any agent can
follow live in [`agents/skills/`](../agents/README.md) and are picked up here
too, since opencode scans `~/.agents/skills` alongside this directory.

## Web access

tmux `prefix o` lazily starts a shared `opencode serve` process on
`127.0.0.1:4096`. The server is kept in the detached `opencode-web` tmux
session and is exposed to mobile devices through Tailscale Serve. Directory-
specific tmux sessions run `opencode attach --dir <path>` against the same
server, so the web UI and terminal clients share project and session state.

tmux `prefix O` reloads only the OpenCode instance associated with the current
pane's project. The next request rebuilds project configuration and discovered
agents, commands, skills, MCP connections, formatters, and language servers;
persisted sessions remain available. Reload is refused while any session in
the project is running or retrying. Project `AGENTS.md` files are already read
on every model turn and normally need no explicit reload.

The project reload cannot refresh already-imported JavaScript or TypeScript
plugins and custom tools because Bun retains its module cache. Restart the
shared server for those changes and for global OpenCode configuration changes.
Restart the directory-specific TUI for `tui.json` or `tui.jsonc` changes.

After enabling Serve for the tailnet, configure its persistent HTTPS proxy:

```sh
tailscale serve --bg 127.0.0.1:4096
```

HTTP Basic authentication is mandatory for `opencode serve`. Store its
password in the macOS Keychain through the existing `opencode` secret layer:

```sh
secret set OPENCODE_SERVER_PASSWORD -p opencode
```

Restart the server after replacing the password; the next tmux `prefix o`
starts it with the new value:

```sh
tmux kill-session -t opencode-web
```

The launcher rejects `opencode serve` when the password is unavailable,
preventing an accidentally unauthenticated web server. Attach clients receive
the same credential through the `opencode` secret shim; it is never placed in
the process arguments.

## Ignored machine state

`node_modules/`, `package.json`, `package-lock.json` and `bun.lock` are
created by opencode when plugins declare npm dependencies — see
[`.gitignore`](./.gitignore).
