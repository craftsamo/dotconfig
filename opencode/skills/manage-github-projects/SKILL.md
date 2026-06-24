---
name: manage-github-projects
description: Use to record and manage persistent, cross-session tasks and notes on a GitHub Projects (v2) "Roadmap" board via the github_project_* tools, instead of writing local TODO/plan/notes files (GitHub Projects, project board, roadmap, draft issue, project item, 起票, タスク管理, ロードマップ, ボードに追加, 進捗更新, ファイルを残さない). Covers the two-tier personal/org board topology and owner resolution, the Status/Kind/Area/_Repository/_Milestone/Phase schema, per-Kind body guidance, and add/start/done/list/note/promote recipes. Use ONLY for GitHub Project board task management, not general gh usage.
---

<Goal>

Persist work items (and their notes) on a GitHub Projects v2 board so they
survive across sessions and are visible on GitHub — without scattering local
`TODO.md` / `plan.md` / notes files. Items are draft issues by default: no repo
issue, no local file, no issue-tracker churn.

</Goal>

<WhenToUse>

- A task, plan, or note should outlive this session or be visible on GitHub →
  put it on the board.
- Ephemeral, within-session step tracking → keep using TodoWrite, not the board.
- Do not create local TODO/plan/notes files for this purpose; use the board.

</WhenToUse>

<Capability>

The board is driven by the generic `github_project_*` custom tools. They resolve
owner / project number / field ids and single-select option ids by NAME at
runtime, so nothing goes stale:

- `github_project_item_add` — add a draft item and set its fields in one call.
- `github_project_item_set` — update fields (e.g. move Status).
- `github_project_item_list` — list / filter items (returns `PVTI_…` item ids).
- `github_project_item_note` — append a note to a draft body.
- `github_project_item_promote` — convert a draft item into a real Issue in a repo.
- `github_project_field_ensure` — idempotently ensure a field / its options.
- `github_project_create` — create a board AND apply the standard Roadmap schema (fields, options, colors) in one call.

`owner` defaults to the current repo's owner (else `@me`); `project` defaults to
a board titled `Roadmap`. Inside a repo you can usually omit both.

</Capability>

<Topology>

Two tiers, chosen by the current repo's owner:

- Personal hub — owner `@me` (craftsamo), board `Roadmap` (#1,
  <https://github.com/users/craftsamo/projects/1>). For your own and
  personal-repo work.
- Shared board — owner = the repo's org. For team repos, so collaborators see
  it. Create on first use and link it to the repo:
  `gh project link <number> --owner <org> --repo <org>/<repo>`.

Resolution rule: if the repo owner is an org you belong to → use that org's
`Roadmap` board (create it if absent); if it is a personal repo or there is no
repo → use the `@me` hub.

</Topology>

<Schema>

| Field | Type | Values |
| --- | --- | --- |
| Status | single-select | Todo / In Progress / Done / Cancelled |
| Kind | single-select | Feature / Enhancement / Bug Fix / Chore / Design / Test |
| Area | single-select | Frontend / Backend / Infra / Docs / UI/UX / Config / CI/CD / Skills / Tooling / Other |
| _Repository | text | `owner/repo` — always set it (the work target) |
| _Milestone | text | Planned milestone title (synced to a real milestone on promote) |
| Phase | number | Optional phase / ordering for large multi-step work |

Naming convention. A leading `_` marks a **draft-time stand-in for a built-in
GitHub field** that cannot be set on a draft; on promote it is reconciled with
the real built-in (synced, then cleared). Only `_Repository` ↔ built-in
Repository and `_Milestone` ↔ built-in Milestone qualify — the built-ins we
carry through promote. Labels / Assignees are deliberately not mirrored (set
them on the real issue after promoting).

Reserved built-in display names — `Title`, `Assignees`, `Labels`, `Milestone`,
`Repository`, `Reviewers`, `Linked pull requests`, `Parent issue`, `Sub-issues
progress`, and `Type` (the issue-type field, present on org boards) — cannot be
created as custom fields. A plain custom field must therefore avoid these names:
that is why the work-kind field is `Kind`, not `Type`/`_Type` — it is an
independent triage taxonomy, not a mirror of GitHub's issue type. `Status` is
the native default project field; `Kind`, `Area` and `Phase` are plain custom
fields.

</Schema>

<ItemModel>

- Default to DRAFT items (file-less, no repo issue). Safe to create, triage, and
  discard — deleting a mistaken draft leaves no trace in any repo's tracker.
- Use a real issue only when the task needs team discussion, assignees, or PR
  linkage. Then create it with the repo's own Issue Form (`gh issue create`) and
  attach it: `gh project item-add <number> --owner <owner> --url <issue-url>`.
- Or promote an existing draft into a real Issue with
  `github_project_item_promote` `{ item, repo }` — the draft title/body become
  the issue, the board item and its fields are kept, the `_Milestone` value (if
  any) is synced to a real repo milestone on the issue, and the now-redundant
  `_Repository` / `_Milestone` fields are cleared automatically.

</ItemModel>

<BodyGuidance>

Compose bodies in GitHub Markdown. Include only the sections that apply — never
leave empty placeholders.

Markup convention:

- `##` — a Kind's main sections (the skeleton you always consider).
- `###` — a sub-section inside a `##`, only when content needs splitting
  (e.g. Option A / Option B, happy path / edge cases, confirmed cause).
- `**Label**:` — a one-line metadata field that doesn't deserve a heading.

Formatting conventions (any item):

- Code reference → a GitHub line-range permalink, not `file:line`:
  `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L16-L37` (commit-pinned, stable).
- Code change → a `diff`-fenced code block.
- Log / long output → wrap in `<details><summary>…</summary> … </details>` with a
  clear summary, so the body stays scannable.
- `**Refs**:` — shared optional inline field for related issue / PR / doc links.

Per Kind (sections in order; fill only the relevant ones):

- Feature
  - `## Purpose` — why build it; the problem it solves.
  - `## Requirements` — functional requirements (bullets); split sub-features with `###`.
  - `## Acceptance criteria` — done checks as a `- [ ]` checklist.
- Enhancement
  - `## Problem` — what is painful or limiting today.
  - `## Change` — what changes and how; show code as a `diff`-fenced block.
  - `## Impact` — affected files / behavior / compatibility (short → `**Impact**:`).
- Bug Fix
  - `## Symptom` — expected vs actual behavior.
  - `## Suspected cause` — likely cause with a line-range permalink; once verified add `### Confirmed cause`.
  - `## Repro steps` — minimal numbered steps.
- Chore
  - `## Summary` — what to do (1–2 lines); add `## Steps` when multi-step.
  - `**Target**:` — files / deps / settings touched.
- Design
  - `## Goal / context` — what is being designed and why.
  - `## Options` — candidates as `### Option A` / `### Option B` with trade-offs.
  - `## Decision` — chosen option and rationale (once decided).
- Test
  - `## Target` — feature / module under test.
  - `## Cases` — cases / angles; split with `### Happy path` / `### Edge cases`.
  - `## Pass criteria` — coverage / pass conditions (optional).

On a shared repo that already provides Issue Forms, prefer that form for real
issues rather than this guidance.

</BodyGuidance>

<Recipes>

Initialize a board (new owner/org):

1. `github_project_create { owner, title: "Roadmap" }` — creates the board (or
   reuses an existing one with that title) and applies the full standard schema
   in one call: Status (incl. Cancelled), Kind and Area with colors, plus
   `_Repository`, `_Milestone`, `Phase`. Idempotent — safe to re-run to repair.
2. Org board only: `gh project link <number> --owner <org> --repo <org>/<repo>`.

`github_project_field_ensure` is only for ad-hoc additions afterwards (e.g. a new
Area option); routine setup is handled by `github_project_create`.

Add an entry of a given Kind:

- Compose the body per `<BodyGuidance>` for that Kind (relevant sections only).
- `github_project_item_add` with
  `{ title, body, fields: { Kind, Area, Status: "Todo", "_Repository": "<owner/repo>" } }`
  (add `"_Milestone"` and/or `"Phase"` for large planned work).

Lifecycle (item id is the `PVTI_…` from `item_list`):

- Start: `github_project_item_set` `{ item, fields: { Status: "In Progress" } }`.
- Done: `github_project_item_set` `{ item, fields: { Status: "Done" } }`.
- Cancel: `github_project_item_set` `{ item, fields: { Status: "Cancelled" } }`.
- Open items: `github_project_item_list` `{ query: "-status:Done -status:Cancelled" }`.
- Note: `github_project_item_note` `{ item, text }`.

Promote a draft to a real Issue (when it becomes tracked team work):

- `github_project_item_promote` `{ item, repo: "<owner/repo>" }` — converts the
  draft to an issue in that repo, keeps it on the board with its field values,
  syncs `_Milestone` to a real repo milestone, and clears `_Repository` /
  `_Milestone` (now redundant).

Add a new Area (or other single-select) option:

- `github_project_field_ensure`
  `{ name: "Area", dataType: "SINGLE_SELECT", options: ["<new option>"] }` —
  it appends, preserving existing options and their ids/colors.

</Recipes>

<Guardrails>

- List before adding to avoid duplicates.
- Keep titles short; put detail in the body.
- Always set `_Repository` from the current repo so the work target is unambiguous.
- Never delete items; archive them in the project UI (there is no delete tool).
- Single-select values must match an existing option name (case-insensitive);
  add the option first with `github_project_field_ensure` if needed.

</Guardrails>
