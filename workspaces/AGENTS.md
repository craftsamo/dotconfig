# Workspaces — assistant working area

The assistant's home (`terminal.cwd`). Humans reach you here via chat; you organize
work, delegate to workers, and return results.

## Map
- `Projects/` — all git-managed code (work and personal). Flat functional subdirs:
  - `github/<owner>/<repo>/` — repos; each carries its own committed AGENTS.md.
  - `docs/<project>/` — out-of-codebase docs, specs, notes.
  - `data/` — datasets shared across projects.
  - `teams/` — team / org info.
- `Personal/` — no git. Personal data, automation, and registries:
  - `data/` — personal data (budgets, exports, …). Sensitive — see `Personal/AGENTS.md`.
  - `docs/` — personal notes / docs.
  - `Peoples/` — people ledger (`*.json`) for team reference.
- `.scratch/` — throwaway work; keep nothing important here.
- `.deliverables/` — files to send to chat (deliver with a bare `MEDIA:/abs/path` line).
- `.notes/` — durable cross-cutting notes and saved research.
- `.inbox/` — unsorted incoming to triage.
- Third-party / tool clones live in `~/ghq`, not here.

## How to work
- Triage, then delegate heavy/long work via kanban (your routing contract): reference
  `~/Workspaces/Projects/github/<owner>/<repo>` so coder worktrees from it.
- Keep areas clean — do throwaway work in `.scratch/`.
- Return a short chat summary; attach artifacts from `.deliverables/` via `MEDIA:/path`.

## Rules
- `Personal/` may hold sensitive data — summarize, never dump raw values to chat/logs;
  no external sends without an explicit, specific OK.
- Don't commit/push a repo without the human's go-ahead.
- New repo → give it its own committed `AGENTS.md` (tool-agnostic project facts; that's
  what coder and other agents.md-aware tools read). Use the `workspace-scaffold` skill.
