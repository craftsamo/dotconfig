# GitHub Copilot

User-level configuration for the GitHub Copilot CLI (`copilot`) and the
desktop app — both installed via the repo [Brewfile](../Brewfile)
(`copilot-cli`, `github-copilot-app`). [`install.sh`](../install.sh) creates
three symlinks into `~/.copilot/`:

| Symlink                              | Target                            |
| ------------------------------------ | --------------------------------- |
| `~/.copilot/copilot-instructions.md` | `copilot/copilot-instructions.md` |
| `~/.copilot/mcp-config.json`         | `copilot/mcp-config.json`         |
| `~/.copilot/agents`                  | `copilot/agents/`                 |

## User-managed content

- `copilot-instructions.md` — local instructions, loaded into every session
- `mcp-config.json` — MCP servers (edited via `copilot mcp` or by hand)
- `agents/*.agent.md` — personal custom agents (markdown + YAML frontmatter;
  created via `/agent` -> "User" or by hand)

Skills are not kept here. Copilot reads the shared `~/.agents/skills` root
(see [`agents/README.md`](../agents/README.md)); `~/.copilot/skills` stays a
real machine-local directory so third-party installer droppings never land
inside the repo.

## Never tracked

- `~/.copilot/config.json` — app-rewritten settings and machine state
  (`trustedFolders` absolute paths, model choice, UI prefs)
- `~/.copilot/` state: logs, session history, memory, `ide/`
- `~/.config/github-copilot/` — auth tokens and sqlite state (git-ignored at
  the repo root); also used by the Neovim Copilot plugin
- The desktop app keeps its own state under `~/Library` and needs no config
  here
