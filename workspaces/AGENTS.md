# Workspaces — assistant working area

The assistant's home (`terminal.cwd`). Humans reach you here via chat; you organize
work, delegate to workers, and return results.

## Map
- `Projects/<Group>/` — git-managed code, grouped by org / client / category. Each
  group holds:
  - `github/<repo>/` — repos (flat under the group; each has its own committed AGENTS.md).
  - `docs/` — out-of-codebase docs, specs, notes.   `data/` — datasets.   `teams/` — team/org info.
- `Personal/<Group>/` — personal data & automation (**no git**). Each group holds:
  - `data/` — data files (e.g. a ledger as `data/*.json`). **Sensitive.**   `docs/` — notes/docs.
- `.scratch/` — throwaway work; keep nothing important here.
- `.deliverables/` — files to send to chat (deliver with a bare `MEDIA:/abs/path` line).
- `.notes/` — durable cross-cutting notes and saved research.
- `.inbox/` — unsorted incoming to triage.
- Third-party / tool clones live in `~/ghq`, not here.

## How to work
- Triage, then delegate heavy/long work via kanban (your routing contract): reference
  `~/Workspaces/Projects/<Group>/github/<repo>` so coder worktrees from it.
- Keep groups clean — do throwaway work in `.scratch/`.
- Return a short chat summary; attach artifacts from `.deliverables/` via `MEDIA:/path`.
- New group/repo → use the `workspace-scaffold` skill.

## Rules
- `Personal/` may hold sensitive data — summarize, never dump raw values to chat/logs;
  no external sends without an explicit, specific OK.
- Don't commit/push a repo without the human's go-ahead.
- New repo → give it its own committed `AGENTS.md` (tool-agnostic project facts; that's
  what coder and other agents.md-aware tools read).
