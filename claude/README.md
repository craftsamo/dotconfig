# Claude Code

User-level configuration for Claude Code. [`install.sh`](../install.sh)
creates four symlinks into `~/.claude/` and links each shared skill into
`~/.claude/skills/`:

| Symlink                      | Target                                                |
| ---------------------------- | ----------------------------------------------------- |
| `~/.claude/CLAUDE.md`        | `claude/CLAUDE.md`                                    |
| `~/.claude/settings.json`    | `claude/settings.json`                                |
| `~/.claude/keybindings.json` | `claude/keybindings.json`                             |
| `~/.claude/commands`         | `claude/commands/`                                    |
| `~/.claude/skills/<name>`    | `~/.agents/skills/<name>` (machine-local shared root) |

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
shared `~/.agents/skills` root — the machine-local mutable dir that
third-party installers write into, holding per-skill links to the
repo-curated tree ([`agents/curated/`](../agents/README.md)). So
`~/.claude/skills` is a real directory with one link per shared skill, each
pointing at the mutable root, not into the repo. It is not linked whole
because Claude Code syncs claude.ai skills into `~/.claude/skills/synced/`
(and retires them to `.trash/`); those need the Claude app's tools and must
not reach the shared root other CLIs read.

## Never tracked

State stays in `~/.claude/` itself: `history.jsonl`, `projects/`,
`sessions/`, `plugins/` (marketplace cache), backups and caches.
