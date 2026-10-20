---
name: gh-projects
description: >-
  Use when work should be visible on a GitHub Projects (v2) board through the
  gh_project_* tools — which board a repository uses (linked → organization →
  personal), setting one up with the standard Status / Start / Target fields
  and Kanban / Backlog / Roadmap views, adding issues or draft notes, moving
  Status, archiving, and turning a draft into an issue (GitHub Projects,
  project board, ボード, ロードマップ, roadmap, Kanban, カンバン, draft item,
  ドラフト, ボードに追加, Status を更新, 進捗更新, タスク管理,
  ファイルを残さない, ideas to track, cross-session plan). The board shows and
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
- Within-session steps → the conversation task list, never the board.
- Writing or changing the issue itself → `gh-issues`.
- Deciding what the work is and how it splits → `approach-github-planning`.

</WhenToUse>

<Tools>

| Tool | Does | Side effects |
| --- | --- | --- |
| `gh_project_resolve` | Which board a call means, the route taken, every route considered, and the board's fields | none |
| `gh_project_item_list` | Items with every field flattened by name and the content's facts; filters by Status, content type, repository, title | none |
| `gh_project_create` | A board by title (reused when present) brought to the standard shape; optional template copy and repository link | creates fields, views, a link |
| `gh_project_link` | Link or unlink a board and a repository | idempotent |
| `gh_project_field_ensure` | A custom field, or missing options on one | never removes |
| `gh_project_view_ensure` | A saved view by name | creates once |
| `gh_project_item_add` | An issue or PR by reference, or a draft by title, with field values | adds |
| `gh_project_item_set` | Field values, clears, a draft's text, archive / restore; the item id names the board | never deletes |
| `gh_project_item_promote` | A draft into an issue of a repository, keeping the item and its fields | creates the issue |

Writers check that the board is writable for the viewer; a repository write
(link, promote) checks that repository too. Archiving is the only way an item
leaves a board.

</Tools>

<Resolution>

Projects are owned by a user or an organization; a repository only links one.
When no `project` is given, every tool takes the same route and reports it:

1. **linked** — a project linked to the repository the call is about (the
   working tree's, or `repo`). One writable linked project is the board;
   among several, only an unambiguous title match (`project: "<title>"`).
2. **org** — the owning organization's open board titled `Roadmap`, when the
   viewer can update it.
3. **user** — the viewer's own open board titled `Roadmap`.

A route is skipped when its board is missing or read-only; when none resolves
the error lists what was considered. `project` pins a board by URL,
`owner/N`, a number with `owner`, or a title (with `owner`, or searched along
the route). Run `gh_project_resolve` once per session before the first write
and read `route` — a write to someone else's board is never a surprise.

Choosing where work lives: a repository you share with a team gets a board
linked to it (the organization's `Roadmap`, or a per-repository board when
the team wants one); your own repositories and ideas without a repository go
on your `Roadmap`. A repository's board is a user- or organization-owned
board linked to it — link it with `gh_project_link` or
`gh_project_create { linkRepo }` so the linked route finds it.

</Resolution>

<Schema>

The standard shape `gh_project_create` ensures; built-in fields carry the rest:

| Field | Type | Holds |
| --- | --- | --- |
| Status | single-select (built-in) | Todo / In Progress / Done / Cancelled |
| Start | date | When work begins; drives the Roadmap view |
| Target | date | When it should land; drives the Roadmap view |

Built-in fields set by GitHub from the issue, never created and set with
`gh-issues` tools: Title, Assignees, Labels, Milestone, Repository, Type,
Parent issue, Sub-issues progress, Linked pull requests. Group or filter
views by them (`parent-issue:"owner/repo#n"`, `milestone:"v1"`,
`repo:owner/repo`). A draft has none of them: it is a title and a body.

Optional custom fields when a board wants them (`gh_project_field_ensure`):
`Area` (single-select, a team's own taxonomy), `Priority`, an iteration
field. Kind is not a board field — it is the issue's type or `type:*` label.

</Schema>

<WhatGoesOnTheBoard>

- **Parent issues** and **standalone issues** always; they are the roadmap.
- **Sub-issues** when their dates or Status matter on their own (a team
  board groups them under `Parent issue`); otherwise the parent's progress
  bar is enough and the board stays readable.
- **Drafts** for ideas: no repository, no issue, no noise in a tracker.
  Promote when the work is decided and a repository is known.
- Never PR-sized slices: a PR is tracked by its PR.

Titles are action phrases (see `gh-issues` `<Titles>`); the detail goes in
the body, not the board.

</WhatGoesOnTheBoard>

<Views>

The standard views `gh_project_create` ensures:

- **Kanban** — board layout by Status, `-status:Done -status:Cancelled`.
- **Backlog** — table, same filter, with Milestone, Parent issue and
  Sub-issues progress as columns.
- **Roadmap** — roadmap layout; bars come from Start / Target once the view
  is bound to them, milestones show as markers.

The API creates a view with its layout, filter and columns only; grouping,
sort, roadmap zoom and the date fields a roadmap reads are set once in the
UI — a freshly created board draws no bars until Start / Target are bound
there. A board copied from a template (`gh_project_create { template }`)
keeps those settings, so keep one configured board per owner to copy from.
`gh_project_view_ensure` adds a view to a board that lacks one and reports
columns the board does not have.

</Views>

<Recipes>

- First use in a repository: `gh_project_resolve {}`. No board on any route
  → `gh_project_create { owner: "<org or @me>", linkRepo: "current" }`,
  with `template` naming a board whose Roadmap view is already bound to
  Start / Target when one exists; otherwise bind the dates once in the UI.
- Capture an idea: `gh_project_item_add { title, body, fields: { Status:
  "Todo" } }` (a draft). Note on it later: `gh_project_item_set { item,
  appendBody }`.
- Decided, repository known: `gh_project_item_promote { item, repo, kind,
  milestone, createMilestone: true }` — then write its body per
  `gh-issues`.
- An issue created elsewhere: `gh_project_item_add { url: "owner/repo#n",
  fields: { Status: "Todo", Target: "2026-12-01" } }`; or let
  `gh_issue_create { addToProject: true }` do it.
- Start / finish / drop: `gh_project_item_set { item, fields: { Status: "In
  Progress" | "Done" | "Cancelled" } }`. The item id comes from
  `gh_project_item_list` or `gh_issue_view` (`projects[].itemId`).
- Schedule: `fields: { Start: "2026-11-01", Target: "2026-11-15" }`.
- What is open: `gh_project_item_list { status: "-Done,-Cancelled" }`; the
  items of this repository: `{ contentRepo: "current" }`.
- Tidy: `gh_project_item_set { item, archived: true }` for a dropped draft or
  a long-closed issue; never delete.
- Re-enter across sessions: `gh_project_item_list { status: "In Progress"
  }` → `gh_issue_view` on the item's issue → its outline and closing PRs say
  where it stopped.

</Recipes>

<Guardrails>

- `gh_project_item_list` before `item_add`: an issue already on the board is
  not added twice.
- Status is the board's; the issue's state is the issue's. Closing an issue
  does not move Status (a workflow may) — set Done when the work is done.
- Built-in fields are set on the issue, never on the board; the tool refuses.
- A draft that gained a repository is promoted, not re-created as an issue
  beside it.
- A write whose `route` is `org` or `user` on a repository you do not own
  lands on a shared or personal board: check that is what was meant.

</Guardrails>
