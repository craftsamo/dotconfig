# Codex

User-level configuration for the Codex CLI / desktop app.
[`install.sh`](../install.sh) creates two symlinks into `~/.codex/`:

| Symlink              | Target           |
| -------------------- | ---------------- |
| `~/.codex/AGENTS.md` | `codex/AGENTS.md` |
| `~/.codex/prompts`   | `codex/prompts/` |

## User-managed content

- `AGENTS.md` — global guidance, loaded into every session
- `prompts/*.md` — custom prompts (`/name`)

Skills are not kept here. Codex reads the shared `~/.agents/skills` root
(see [`agents/README.md`](../agents/README.md)); `~/.codex/skills` stays a
real machine-local directory so app-seeded content (`skills/.system/`) and
third-party installer droppings never land inside the repo.

## Intentionally untracked

- `config.toml` — the Codex app rewrites it with machine-specific absolute
  home paths (marketplace and runtime registrations), so it is git-ignored
  and stays local to each machine. Codex regenerates it on a fresh install.
- `~/.codex/skills/` — machine-local (app-managed `.system/` plus installer
  mirrors); nothing in the repo.
- Auth and state (`~/.codex/auth.json`, sqlite logs, transcripts) live in
  `~/.codex/` itself and never enter the repo.
