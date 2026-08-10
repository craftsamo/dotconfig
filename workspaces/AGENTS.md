# Workspaces — assistant working area

The assistant's home (`terminal.cwd`). Humans reach you here via chat; you organize
work, delegate to workers, and return results.

## Map
- `Projects/<Group>/` — flat canonical groups for project code and material. An
  organization is a registry reference, never a parent directory. Each group holds:
  - `github/<repo>/` — repos (flat under the group; each has its own committed AGENTS.md).
  - `docs/` — out-of-codebase docs, specs, notes.   `data/` — datasets.   `assets/` —
    local media (logos, screenshots, generated material) that must NOT be committed
    into the repos; optional, on demand.
  - `.agent/{scratch,deliverables,notes}/` — group-local agent work, created on demand;
    never place it under `github/<repo>/`.
  - Group identity, primary organization, repos, links, **team memberships**, tags →
    central `Projects/.registry/` (the `projects` skill / `pj`), not per-group files.
- `Personal/<Group>/` — personal data & automation (**no git**). Typed subdirs,
  entity-namespaced (same slug across trees, e.g. `data/<slug>/`):
  - `data/` — structured records. **Sensitive.** Not a catch-all.   `docs/` — notes/docs.
  - Optional, on demand: `assets/` — reusable reference media.   `scripts/` — group
    automation.   `archive/` — quarantine for unadopted/rogue outputs (adoption needs
    explicit human agreement; see `Personal/AGENTS.md`).
  - `.agent/{scratch,deliverables,notes}/` — sensitive group-local agent work, created
    on demand.
- `.scratch/` — fallback throwaway work for unassigned or cross-group tasks only.
- `.deliverables/` — fallback chat-delivery staging for unassigned or cross-group tasks.
- `.notes/` — durable cross-cutting notes and saved research with no single owner.
- `.inbox/` — unsorted incoming to triage.
- Third-party / tool clones live in `~/ghq`, not here.

## How to work
- Triage, then delegate heavy/long work via kanban (your routing contract): reference
  `~/Workspaces/Projects/<Group>/github/<repo>` so coder worktrees from it.
- Resolve the owning Group before writing. For one owner, use
  `<Group>/.agent/{scratch,deliverables,notes}/`; use the root fallbacks only when work
  is unassigned or intentionally spans Groups.
- Work in `.agent/scratch/<job>/`. After producer verification, promote final files to
  `.agent/deliverables/<job>/` for Assistant QA and reusable evidence to
  `.agent/notes/` or `assets/`. At promotion, delete only reproducible caches; keep
  variants and useful revision inputs until the user accepts the delivery, but never
  leave the only copy of anything important in scratch.
- Return a short chat summary; attach artifacts from the selected `deliverables/` via
  `MEDIA:/path`. After acceptance, promote canonical keepers to `docs/`, `data/`,
  `assets/`, or a repo as appropriate, then clear that job's `scratch/` and
  `deliverables/`. Durable `notes/` remain.
- Existing root state is a migration backlog, not a reason to keep routing new work
  there. Never bulk-move it by filename alone: classify one touched job at a time,
  verify file counts and byte identity in the Group-local copy, then remove only that
  old job after acceptance.
- Keep canonical Groups flat. Use `pj organization-set` and
  `pj list --organization` to organize them; never infer organization from a path or
  create `Projects/<Organization>/<Group>/`.
- New group/repo → use the `workspace-scaffold` skill.

## Rules
- `Personal/` may hold sensitive data — summarize, never dump raw values to chat/logs;
  no external sends without an explicit, specific OK.
- Don't commit/push a repo without the human's go-ahead.
- New repo → give it its own committed `AGENTS.md` (tool-agnostic project facts; that's
  what coder and other agents.md-aware tools read).
