# Projects — git-managed code

Flat functional layout (not per-project folders):
- `github/<owner>/<repo>/` — the repos. Each repo owns a committed, **tool-agnostic**
  `AGENTS.md` (architecture, build/test/run, conventions). That file is shared context
  for every agents.md-aware tool (Hermes coder, OpenCode, Codex, Cursor) — keep
  tool-specific instructions out of it.
- `docs/<project>/` — design notes, specs, and out-of-codebase docs per project.
- `data/` — datasets shared across projects.
- `teams/` — team / org info.

## How to work
- The assistant coordinates: create a kanban task referencing the repo path; coder
  worktrees from `github/<owner>/<repo>`. Don't do large refactors inline in chat.
- Don't commit/push without the human's go-ahead. Throwaway work goes in `../.scratch/`.
- Add a repo with the `workspace-scaffold` skill (makes `github/<owner>/<repo>`,
  `git init`, and seeds the repo `AGENTS.md` from the template).
