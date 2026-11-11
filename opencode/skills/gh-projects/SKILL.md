---
name: gh-projects
description: >-
  Use for the house conventions of GitHub Projects (v2) boards — what goes on
  a board, which board a repository uses, the standard Status / Start / Target
  schema and Kanban / Backlog / Roadmap views, Status discipline, draft items
  and when they become issues, and the recipes for adding, moving and
  archiving items (GitHub Projects, project board, ボード, ロードマップ,
  roadmap, Kanban, カンバン, draft item, ドラフト, ボードに追加,
  Status を更新, 進捗更新, タスク管理, ファイルを残さない, ideas to track,
  cross-session plan). The tool mechanics are in the package skill
  `github-projects`; load it together with this one. The board shows and
  schedules; the issue is the record (gh-issues). Not for decomposing a
  requirement (approach-github-planning) or within-session step tracking.
author: CraftSamo
license: MIT
---

<Goal>

Make durable work visible and schedulable on a GitHub Projects board without
local TODO / plan / notes files: the board is where a person or a later
session sees what is open, what is next and when, while the issue stays the
record of what the work is. Ideas that have no repository yet live on the
board as drafts until they become issues.

</Goal>

<WhenToUse>

- Work should outlive the session or be seen by others → the board.
- An idea is worth keeping but not yet worth an issue → a draft on the board.
- Within-session steps → the session's todo list (`todowrite`), never the board.
- Writing or changing the issue itself → `gh-issues`.
- Deciding what the work is and how it splits → `approach-github-planning`.
- A run Hermes commissions → its operating note, not this skill, decides
  which board writes are yours (`AGENTS.md` `<SessionLocation>`).

</WhenToUse>

<Tools>

Load `github-projects` for the tools, how a board is named and found, and how
a call fails. Every write asks the person once, with a description of what it
will change. This skill's recipes use `github_project_read` (`view`,
`item_list`), `github_project_create`, `github_project_link`,
`github_project_field_ensure`, `github_project_view_ensure`,
`github_project_item_add`, `github_project_item_create`,
`github_project_item_edit`, `github_project_item_archive` and
`github_project_item_convert`, with `github_issue_read` for an issue's board
items. Archiving is the only way an item leaves a board.

</Tools>

<Resolution>

Projects are owned by a user or an organization; a repository only links one.
Each board tool names its board (`project`: number, `owner/N`, URL or title;
`Roadmap` when none is given) and finds it among the boards linked to the
repository, then the organization's, then the viewer's (`github-projects`
`Naming a board`). Run `github_project_read { method: "view" }` once per
session before the first write and read `route`, so a write to someone
else's board is never a surprise.

Choosing where work lives: a repository you share with a team gets a board
linked to it (the organization's `Roadmap`, or a per-repository board when
the team wants one); your own repositories and ideas without a repository go
on your `Roadmap`. A repository's board is a user- or organization-owned
board linked to it — link it with `github_project_link` or
`github_project_create { link_repo }` so the linked route finds it.

</Resolution>

<Schema>

The standard shape `github_project_create` ensures; built-in fields carry the rest:

| Field | Type | Holds |
| --- | --- | --- |
| Status | single-select (built-in) | Todo / In Progress / Done / Cancelled; a board may add `Waiting` (on someone outside) with `github_project_field_ensure` |
| Start | date | When work begins; drives the Roadmap view |
| Target | date | When it should land; drives the Roadmap view |

Built-in fields set by GitHub from the issue, never created and set with
`gh-issues` tools: Title, Assignees, Labels, Milestone, Repository, Type,
Parent issue, Sub-issues progress, Linked pull requests. Group or filter
views by them (`parent-issue:"owner/repo#n"`, `milestone:"v1"`,
`repo:owner/repo`). A draft has none of them: it is a title and a body.

Optional custom fields when a board wants them (`github_project_field_ensure`):
`Area` (single-select, a team's own taxonomy), `Priority`, an iteration
field. Kind is not a board field — it is the issue's type or `type:*` label.

</Schema>

<WhatGoesOnTheBoard>

- **Parent issues** and **standalone issues** always; they are the roadmap.
- **Sub-issues** when their dates or Status matter on their own (a team
  board groups them under `Parent issue`); otherwise the parent's progress
  bar is enough and the board stays readable.
- **Drafts** for work that has no reason to be an issue yet (below).
- Never PR-sized slices: a PR is tracked by its PR.
- Never questions put to someone outside: they live where they are asked (a
  message, a shared sheet). An answer that creates work becomes a draft.

Titles are action phrases (see `gh-issues` `<Titles>`); the detail goes in
the body, not the board, in the forms of `gh-issues` `<Notation>`. In a
draft a code permalink stays a plain link and a mention notifies nobody, so
a code link carries its own text (`[path#L3-L9](permalink)`) and a person
who must know is told elsewhere.

**Draft or issue.** Keep an item a draft while any of these holds: whether
it will be done is not decided; it has no repository to live in; its
repository is not yet one your side works in. A draft holds the title, why
the work exists, links to where it came from, and dated notes appended as
things happen; order goes in one line each ("Together with: …", "After: …").
A draft may end Done without ever becoming an issue when the work never
touches a repository; its last note records what proves it done.

Turn a draft into an issue (`github_project_item_convert`) when any of these
becomes true: its target is a repository your side works in; it needs a PR,
an assignee who works in GitHub, or discussion there; it has grown steps
worth tracking as sub-issues. Then rewrite its body in the issue form
(`gh-issues` `<Bodies>`), move the draft's notes under `## Evidence`, and turn
its "After:" lines into blocked-by.

Never put a secret value, a key's location or someone's private remarks on a
board or in an issue: a board can be made public later.

</WhatGoesOnTheBoard>

<Views>

The standard views `github_project_create` ensures:

- **Kanban** — board layout by Status, `-status:Done -status:Cancelled`.
- **Backlog** — table, same filter, with Milestone, Parent issue and
  Sub-issues progress as columns.
- **Roadmap** — roadmap layout; bars come from Start / Target once the view
  is bound to them, milestones show as markers.

The API creates a view with its layout, filter and columns only; grouping,
sort, roadmap zoom and the date fields a roadmap reads are set once in the
UI — a freshly created board draws no bars until Start / Target are bound
there. A board copied from a template (`github_project_create { template }`)
keeps those settings, so keep one configured board per owner to copy from.
`github_project_view_ensure` adds a view to a board that lacks one and reports
columns the board does not have.

</Views>

<Recipes>

- First use in a repository: `github_project_read { method: "view" }`. No
  board on any route → `github_project_create { owner: "<org or @me>",
  link_repo: "<owner/name>" }`, with `template` naming a board whose Roadmap
  view is already bound to Start / Target when one exists; otherwise bind the
  dates once in the UI.
- Capture an idea: `github_project_item_create { title, body, fields: {
  Status: "Todo" } }` (a draft). Note on it later:
  `github_project_item_edit { item, append_body }`.
- Decided, repository known: `github_project_item_convert { item, repo, kind,
  milestone, create_milestone: true }` — then write its body per
  `gh-issues`.
- An issue created elsewhere: `github_project_item_add { item:
  "owner/repo#n", fields: { Status: "Todo", Target: "2026-12-01" } }`; or let
  `github_issue_create { project, fields }` do it.
- Start / finish / drop: `github_project_item_edit { item, fields: { Status:
  "In Progress" | "Done" | "Cancelled" } }`. The item names itself by its id
  from `github_project_read` `item_list` or `github_issue_read` `view`
  (the issue's boards), or by the issue's reference.
- Schedule: `fields: { Start: "2026-11-01", Target: "2026-11-15" }`.
- What is open: `github_project_read { method: "item_list", status:
  "-Done,-Cancelled" }`; the items of this repository: `{ content_repo:
  "<owner/name>" }`.
- Tidy: `github_project_item_archive { item }` for a dropped draft or a
  long-closed issue; never delete.
- Re-enter across sessions: `github_project_read { method: "item_list",
  status: "In Progress" }` → `github_issue_read` `view` on the item's issue →
  its outline and closing PRs say where it stopped.

</Recipes>

<Guardrails>

- `github_project_read` `item_list` before `github_project_item_add`: an
  issue already on the board is not added twice (the tool also returns the
  existing item).
- Status is the board's; the issue's state is the issue's. Closing an issue
  does not move Status (a workflow may) — set Done when the work is done.
- Built-in fields are set on the issue, never on the board; the tool refuses.
- A draft that gained a repository is converted, not re-created as an issue
  beside it.
- A board found by the organization or viewer lookup, for a repository you
  do not own, is a shared or personal board: check that is what was meant.

</Guardrails>
