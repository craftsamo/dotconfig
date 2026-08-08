# Claude Code

User-level configuration for Claude Code. [`install.sh`](../install.sh)
creates five symlinks into `~/.claude/`:

| Symlink                      | Target                    |
| ---------------------------- | ------------------------- |
| `~/.claude/CLAUDE.md`        | `claude/CLAUDE.md`        |
| `~/.claude/settings.json`    | `claude/settings.json`    |
| `~/.claude/keybindings.json` | `claude/keybindings.json` |
| `~/.claude/commands`         | `claude/commands/`        |
| `~/.claude/skills`           | `~/.agents/skills/` (machine-local shared root) |

## User-managed content

- `CLAUDE.md` — global instructions, loaded into every session
- `settings.json` — permissions, hooks, model defaults
- `keybindings.json` — custom key bindings
- `commands/*.md` — personal slash commands (`/name`; `$ARGUMENTS` expands
  to the command arguments)

`~/.claude/agents` is machine-local, not linked: app installers (tldraw
Desktop's agent-skills setup, for one) replace the symlink with a real
directory and drop their subagent files into it, so a repo link only
produced recurring drift warnings. Repo-curated subagents do not exist
today; if one appears, give it a dedicated linked file rather than
re-linking the whole directory.

Skills are not kept here. Claude Code is the only CLI that does not read the
shared `~/.agents/skills` root, so its skill dir is bridged to that root —
the machine-local mutable dir that third-party installers write into, holding
per-skill links to the repo-curated tree
([`agents/curated/`](../agents/README.md)). The bridge deliberately points at
the mutable root, not into the repo.

## Never tracked

State stays in `~/.claude/` itself: `history.jsonl`, `projects/`,
`sessions/`, `plugins/` (marketplace cache), backups and caches.
