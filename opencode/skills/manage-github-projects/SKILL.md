---
name: manage-github-projects
description: Use to record and manage persistent, cross-session tasks and notes on a GitHub Projects (v2) "Roadmap" board via the github_project_* tools, instead of writing local TODO/plan/notes files (GitHub Projects, project board, roadmap, draft issue, project item, 起票, タスク管理, ロードマップ, ボードに追加, 進捗更新, ファイルを残さない). Covers the two-tier personal/org board topology and owner resolution, the Status/Kind/Area/_Repository/_Milestone schema, board granularity (epic / sub-issue), saved views (Kanban / Backlog / roadmap via a copied template), per-Kind body guidance, and add/start/done/list/note/promote recipes. Use ONLY for GitHub Project board task management, not general gh usage.
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
- For the planning workflow that feeds the board (epic vs single item, phasing,
  the promote → branch → PR lifecycle), see the `approach-github-projects`
  skill.

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
- `github_project_view_ensure` — idempotently ensure a saved view (table/board/roadmap + filter/columns) via the REST views API.
- `github_project_create` — create a board AND apply the standard Roadmap schema; a new board is seeded by copying the "Roadmap Template" (carrying its saved views).

Issue lifecycle (take an issue number, typically from `github_project_item_promote`'s return; operate on the current repo or `repo`):

- `github_project_issue_link` — link sub-issues under a parent (epic) or unlink them; sets each sub-issue's Issue Type to `Task` on link (best-effort). `gh >= 2.94.0`.
- `github_project_issue_develop` — create (or reuse) a linked development branch for an issue; a PR from it links in the Development panel automatically.

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
| _Milestone | text | Theme that groups epics — milestone title, synced to a real milestone on promote |
| Start date | date | Drives the roadmap (Timeline) views |
| Target date | date | Drives the roadmap (Timeline) views |

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
the native default project field; `Kind` and `Area` are plain custom fields.

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

<Granularity>

What goes on the board, and how large work is broken down:

- A board item is a **standalone task** or an **epic** — never the individual
  sub-tasks of an epic. Keep the board a roadmap of efforts, not a flat task dump.
- Break large multi-step work into an **epic**: one parent issue whose body follows
  the Epic format in `<BodyGuidance>` (Overview + a phased Plan — ordering / waves
  live here in prose, there is no Phase field). Its steps are GitHub **sub-issues**
  in the relevant repo.
- Sub-issues stay in the repo and are **not** added to the board; they are
  single-purpose and use the repo's own Issue template. Link each under the epic
  with `github_project_issue_link` (it also sets the sub-issue's Issue Type to
  `Task`). Progress shows on the epic via its sub-issue bar (e.g. `2/5`).
- **Milestone** is a high-level **theme** grouping epics over time. Assign it to the
  **epic**, not to each sub-task; a later epic on the same theme joins the same
  milestone while it is open.

</Granularity>

<Views>

GitHub's API cannot fully configure views: layout, filter and visible columns are
settable (REST), but grouping, sort, and the roadmap zoom / date-binding are
UI-only. So the standard views are configured once on the `@me` "Roadmap
Template" board, and `github_project_create` **copies** that template for every
new board — carrying the views intact.

Standard views (3):

- **Timeline** — roadmap layout driven by `Start date` / `Target date`; the month zoom is set in the UI.
- **Kanban** — board layout, filter `-status:Done -status:Cancelled` (groups by Status by default).
- **Backlog** — table layout, filter `-status:Done -status:Cancelled`, columns Title / Kind / Area / Status.

`github_project_view_ensure` `{ name, layout, filter?, visibleFields? }` adds a
table/board view to an existing board (idempotent by name) — use it to repair a
board that predates the template. It cannot set grouping/sort/zoom; finish
roadmap views in the UI on the template.

</Views>

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

Common optional section (any Kind, when the work will be implemented):

- `## Approach` — the implementation outline: main steps, the files / modules it
  touches, and the chosen approach. Outline only — NO code blocks (the PR diff is
  the implementation; code here drifts from it). Lets a sub-issue be picked up by
  an agent or a fresh session without re-exploring the codebase. Omit when
  Requirements / Acceptance already make the work obvious. Distinct from an
  epic's `## Plan` (which orders sub-issues into phases).

Epic (a parent issue with sub-issues — any Kind; supersedes the per-Kind body):

- `## Overview` — the outcome and why (1–3 lines).
- `## Details` — scope / constraints / design notes (optional; omit if none).
- `## Plan` — phased breakdown: `### Phase 1 — <wave goal>` then plain `- #12`
  sub-issue references; add `### Phase 2 …` for later waves.
- `## Acceptance` — the integration-level checks confirmed AFTER all sub-issues
  land (end-to-end scenarios, requirement coverage, no regressions). Use `- [ ]`
  checkboxes here. This is the epic's exit criterion; each sub-issue's own
  acceptance lives in that sub-issue, not here.
- Reference sub-issues in `## Plan` as `#n` only — no `- [ ]` there (the native
  Sub-issues panel is the single source of progress; checkboxes create a
  parallel task list). Checkboxes belong ONLY in `## Acceptance`.
- Phase grouping is maintained by hand; update Plan when sub-issues change.

On a shared repo that already provides Issue Forms, prefer that form for real
issues rather than this guidance.

</BodyGuidance>

<Recipes>

Initialize a board (new owner/org):

1. `github_project_create { owner, title: "Roadmap" }` — seeds the board by
   copying the `@me` "Roadmap Template" (carrying its saved views) when present,
   else creates it bare, then applies the full standard schema: Status (incl.
   Cancelled), Kind and Area with colors, `_Repository`, `_Milestone`, and
   `Start date` / `Target date`. Idempotent — safe to re-run to repair.
2. Org board only: `gh project link <number> --owner <org> --repo <org>/<repo>`.

`github_project_field_ensure` / `github_project_view_ensure` are for ad-hoc
additions afterwards (a new Area option, or a view on a pre-template board);
routine setup is handled by `github_project_create`.

Add an entry of a given Kind:

- Compose the body per `<BodyGuidance>` for that Kind (relevant sections only).
- `github_project_item_add` with
  `{ title, body, fields: { Kind, Area, Status: "Todo", "_Repository": "<owner/repo>" } }`
  (add `"_Milestone"` to file it under a theme; for large multi-step work use an
  epic — see `<Granularity>`).

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

After promote — wire the issue into the development lifecycle (the
`approach-github-projects` skill decides when each applies):

- Branch + Development link: `github_project_issue_develop`
  `{ issue, branch?, base?, checkout?, repo? }` — creates a linked development
  branch (or reuses an existing one); a PR opened from it links in the issue's
  Development panel automatically. For an epic's sub-issue, point `base` at the
  epic branch so the PR stacks under it.
- Sub-issue under an epic: `github_project_issue_link`
  `{ parent, subs, subType?: "Task" }` — links the sub-issues under the parent
  and sets each sub's Issue Type to `Task` (best-effort: warns and continues on
  repos without Issue Types).

Add a new Area (or other single-select) option:

- `github_project_field_ensure`
  `{ name: "Area", dataType: "SINGLE_SELECT", options: ["<new option>"] }` —
  it appends, preserving existing options and their ids/colors.

</Recipes>

<Guardrails>

- List before adding to avoid duplicates.
- Titles are action phrases (JA「〜する」, EN imperative) stating the work to do,
  not a noun or a bare symptom — for a bug, name the fix (「〜を修正する」). Keep
  them short and put detail in the body. e.g.「ルートの README.md を整備する」.
- Always set `_Repository` from the current repo so the work target is unambiguous.
- Never delete items; archive them in the project UI (there is no delete tool).
- Single-select values must match an existing option name (case-insensitive);
  add the option first with `github_project_field_ensure` if needed.

</Guardrails>
