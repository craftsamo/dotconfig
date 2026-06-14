# Projects — git-managed code (grouped)

Each subdirectory is a **group** (org / client / category). A group holds:
- `github/<repo>/` — the repos, flat under `github/` (the group is the owner). Each repo
  owns a committed, **tool-agnostic** `AGENTS.md` (architecture, build/test/run,
  conventions) — shared context for every agents.md-aware tool (Hermes coder, OpenCode,
  Codex, Cursor). Keep tool-specific instructions out of it.
- `docs/` — design notes, specs, out-of-codebase docs.
- `data/` — datasets.
- `teams/` — team / org info.

## How to work
- Coordinate: create a kanban task referencing `Projects/<Group>/github/<repo>`; coder
  worktrees from it. Don't do large refactors inline in chat.
- Don't commit/push without the human's go-ahead. Throwaway work goes in `../.scratch/`.
- Add a group/repo with the `workspace-scaffold` skill:
  `ws-new.sh group projects <Group>` then `ws-new.sh repo <Group> <repo>`.
