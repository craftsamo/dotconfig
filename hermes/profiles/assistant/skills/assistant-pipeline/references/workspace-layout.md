# Workspace layout and drafts

Shared rules for locating work under `~/Workspaces` and for handling drafts.
This reference owns these facts; other documents point here.

## Map

- `Projects/<Group>/` — flat canonical groups for project code and material. An
  organization is a registry reference, never a parent directory. Each group holds:
  - `github/<repo>/` — repos (flat under the group; each has its own committed AGENTS.md).
  - `docs/` — out-of-codebase docs, specs, notes.   `data/` — datasets.   `assets/` —
    local media (logos, screenshots, generated material) that must NOT be committed
    into the repos; optional, on demand.
  - `.agent/<YYYYMMDD>-<job>/` — drafts (see "Drafts"); never under `github/<repo>/`.
  - Group identity, primary organization, repos, links, **team memberships**, tags →
    the workspace registry (below), not per-group files.
- `Personal/<Group>/` — personal data & automation (**no git**). Typed subdirs,
  entity-namespaced (same slug across trees, e.g. `data/<slug>/`):
  - `data/` — structured records. **Sensitive.** Not a catch-all.   `docs/` — notes/docs.
  - Optional, on demand: `assets/` — reusable reference media.   `scripts/` — group
    automation.   `archive/` — quarantine for unadopted/rogue outputs (adoption needs
    explicit human agreement).
  - `.agent/<YYYYMMDD>-<job>/` — sensitive drafts (see "Drafts").
- `.agent/<YYYYMMDD>-<job>/` — drafts of unassigned or intentionally cross-group work.
- `.inbox/` — unsorted incoming to triage.
- `.registry/*.csv` — the workspace registry: people (identity, aliases, contacts,
  languages), projects (Groups and organizations), memberships and repos. Read and write
  it only with the `workspace_registry` tool, never a terminal command or a file edit.
  Before calling the registry, read `skill_view(name="workspace-registry:workspace-registry")`
  for its plugin-owned operation procedures.
  **Sensitive** like `Personal/`: people records and member calibration
  (`working_relationship`, notes) are summarized, never pasted raw into chat or logs.
- Third-party / tool clones live in `~/ghq`, not here.

## Drafts

Where a file sits is its status. There is no job record, state file or log.

- **Everything under an `.agent/` is a draft**: intermediate, non-canonical, and
  deletable. Canon lives only in a Group's `docs/`, `data/`, `assets/` or
  `github/<repo>`.
- **One job, one directory: `.agent/<YYYYMMDD>-<job>/`.** The date is the local
  day the job started; `<job>` is a short kebab-case slug. The whole job — every
  session, profile and revision — uses that one directory, with any subdirectories
  it needs. No session ID in the name. Resolve the owning Group first; use the root
  `~/Workspaces/.agent/` only when no single Group owns the work.
- **Never read a draft as canon.** Take facts and decisions from the canonical
  surfaces. A draft from an earlier session is at most material to re-check, never
  a source to cite.
- **Promotion is the only way into canon.** When a job is delivered, the Assistant
  proposes each keeper with its canonical destination (research findings and
  decisions go to the Group's `docs/`) and the user approves. Then move, check that
  file counts and bytes match, and delete the job's draft directory. Unassigned work
  gets its owning Group chosen at promotion; the root has no canonical surface.
- **A draft that remains is work not yet promoted.** Deleting a draft without
  promotion also needs the user's OK. The `workspace_drafts` tool (`/drafts`,
  `ws-drafts` in a shell) lists every draft with its age, size and flags
  (`stale`, `misnamed`, `legacy`); it only reads. `/drafts inbox` lists what
  waits in `.inbox/` (never a draft), stale once a file has waited 7 days.
- Deliver from the draft with a bare `MEDIA:/abs/path` line.
- The earlier layout (`.scratch/`, `.deliverables/`, `.notes/` at the root and
  `.agent/{scratch,deliverables,notes}/` in Groups) is retired: never start work
  there. `workspace_drafts` flags what remains as `legacy` — a job still finishing
  in place, or a stray write. Do not move a legacy job while it is in use; clean it
  up with the user once it is done.
