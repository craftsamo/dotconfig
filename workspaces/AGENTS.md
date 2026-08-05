# Workspaces — assistant working area

The assistant's home (`terminal.cwd`). Humans reach you here via chat; you organize
work, delegate to workers, and return results.

## Map
- `Projects/<Group>/` — git-managed code, grouped by org / client / category. Each
  group holds:
  - `github/<repo>/` — repos (flat under the group; each has its own committed AGENTS.md).
  - `docs/` — out-of-codebase docs, specs, notes.   `data/` — datasets.   `assets/` —
    local media (logos, screenshots, generated material) that must NOT be committed
    into the repos; optional, on demand.
  - Group identity, repos, links, **team memberships**, tags → central `Projects/.registry/`
    (the `projects` skill / `pj`), not per-group files.
- `Personal/<Group>/` — personal data & automation (**no git**). Typed subdirs,
  entity-namespaced (same slug across trees, e.g. `data/<slug>/`):
  - `data/` — structured records. **Sensitive.** Not a catch-all.   `docs/` — notes/docs.
  - Optional, on demand: `assets/` — reusable reference media.   `scripts/` — group
    automation.   `archive/` — quarantine for unadopted/rogue outputs (adoption needs
    explicit human agreement; see `Personal/AGENTS.md`).
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
