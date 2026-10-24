---
name: gh-issues
description: >-
  Use when creating, reading, updating, relating or closing GitHub Issues
  through the gh_issue_* tools — an issue's body by kind, a parent issue with
  sub-issues, a milestone, blocked-by / blocking dependencies, the Draft →
  Fixed spec of an issue about to be implemented, progress and decision
  comments, closing with a reason, and replacing issues without losing their
  content (Issue, イシュー, 起票, Issue を立てる, sub-issue, 親 Issue, 子 Issue,
  parent issue, milestone, マイルストーン, blocked by, 依存関係, issue type,
  ラベル, Issue を閉じる, close issue, Issue にコメント). Owns the planning
  model's issue side: parent issue + sub-issues for structure, milestone for
  time, blocked-by for order, kind as Issue Type or type:* label. Not for
  boards (gh-projects), PRs (git-pullrequest) or decomposing a requirement
  (approach-github-planning).
author: CraftSamo
license: MIT
---

<Goal>

Keep work on GitHub Issues in a shape that a fresh session, a teammate or an
agent can pick up without the conversation that produced it: one issue per
unit of work, its structure in GitHub's own relations (parent, sub-issues,
milestone, blocked by, type) rather than in body text, a body that says what
done means, and a close that says why.

</Goal>

<WhenToUse>

- Record, read, change, relate, comment on or close an issue → this skill and
  the `gh_issue_*` tools.
- Decide whether work is one issue, a parent with sub-issues, or a stack of
  PRs, and run it → `approach-github-planning` (it calls back here for the
  issue mechanics).
- Put an issue on a board, move its Status, or capture an idea that has no
  repository yet → `gh-projects`.
- Open or update a PR, decide `Refs` vs `Closes` → `git-pullrequest`.
- Within-session step tracking → the session's todo list (`todowrite`), never an issue.

</WhenToUse>

<Tools>

| Tool | Does | Side effects |
| --- | --- | --- |
| `gh_issue_view` | The whole picture of one issue: body, kind, milestone, parent, sub-issues and progress, blocked by / blocking, linked branches, closing PRs, board items (with `PVTI_…` ids), latest comments | none |
| `gh_issue_list` | Issues of a repository by state, kind, milestone, label, assignee, free search; or a parent's sub-issues | none |
| `gh_issue_create` | Issue + kind + milestone + parent + blocked-by + board item in one call | creates the issue; later steps report under `errors` without losing it |
| `gh_issue_update` | Title, body (replace or append), kind, labels, assignees, milestone, close with a reason, reopen | edits; a close needs `reason` |
| `gh_issue_comment` | A comment | posts |
| `gh_issue_relate` | Parent set / removed, sub-issues and dependencies added / removed | idempotent against the current relations |
| `gh_issue_develop` | A linked development branch, or the one that exists | creates a branch; see `<ClosingReferences>` |

Every writer checks the viewer's write permission first and reports a
repository the viewer does not own as `foreign: true`; nothing deletes. The
sub-issue, type and dependency flags need `gh` 2.94.0 or later. Issues are
named as `12`, `#12`, `owner/repo#12` or a URL; a bare number means the
working tree's repository unless `repo` is passed.

</Tools>

<Model>

GitHub's own relations carry the structure; nothing is duplicated in text:

| Need | Use | Not |
| --- | --- | --- |
| A unit of work | an **issue** — one branch or one native stack of PRs implements it | a checklist line in another issue |
| A goal made of several units | a **parent issue** with sub-issues (100 per parent, 8 levels; a sub-issue may live in another repository of the same owner) | an epic label, a `Parent: #n` line |
| When / which release | a **milestone** (repository-scoped; set it on the parent and on each sub-issue that has its own date) | a date in the title |
| Order between siblings | **blocked by** on the later issue (boards show a Blocked marker) | a wave table that goes stale |
| What sort of work | **kind**: an Issue Type on an organization repository that defines it (task / bug / feature by default), a `type:<kind>` label elsewhere — the tools pick per kind, so an organization repository mixes types and labels unless it defines every kind it uses | a `Kind` board field |
| How far along | the board's Status, the parent's sub-issue progress bar, the issue's `## Implementation outline` checklist, its state | a percentage or a status line in the body |

Parent issues track; they have no branch and no stack. A parent is right when
the goal decomposes into several units that each deliver something on their
own; a parent that would decompose straight into five or more PR-sized pieces
is missing a tier — insert sub-issues that are goals, not PRs. Below an issue
the unit is a PR (a stack layer), never another issue: the PR holds the diff,
the checks and the review beside its slice of the spec.

</Model>

<Titles>

An action phrase stating the work (EN imperative, JA「〜する」), short, with
the detail in the body. For a bug, name the fix. e.g. "Retry the upload once
on a 5xx", 「ルートの README.md を整備する」. Not a noun, not a bare symptom.

</Titles>

<Bodies>

GitHub Markdown; only the sections that apply, never an empty placeholder.
`##` for a kind's main sections, `###` to split one, `**Label**:` for a
one-line field. References, code, logs and links take the forms in
`<Notation>`; code changes are `diff` fences. `**Refs**:` holds related
issues, PRs and docs. Write section names in the repository's language; the
meaning stays 1:1 with the English below. Never write `Parent: #n` — the
sub-issue panel is the one source of parentage. Reference siblings as `#n`
and create issues in dependency order so the numbers exist.

Per kind:

- **feature** — `## Purpose` (the problem it solves) · `## Requirements`
  (bullets; `###` per sub-feature) · `## Acceptance criteria` (`- [ ]`).
- **enhancement** — `## Problem` · `## Change` (a `diff` fence when code) ·
  `## Impact` (files, behavior, compatibility; `**Impact**:` when short).
- **bug** — `## Symptom` (expected vs actual) · `## Suspected cause` (permalink;
  add `### Confirmed cause` once verified) · `## Repro steps`.
- **chore** / **task** — `## Summary` (1–2 lines; `## Steps` when several) ·
  `**Target**:` (files, deps, settings).
- **design** — `## Goal / context` · `## Options` (`### Option A` …, with
  trade-offs) · `## Decision` (once taken).
- **test** — `## Target` · `## Cases` (`### Happy path` / `### Edge cases`) ·
  `## Pass criteria`.

Any kind that will be implemented may add `## Approach`: the outline of the
implementation (steps, files, chosen approach) — no code blocks; the PR diff
is the implementation. Omit it when Requirements already make the work plain.

**Parent issue** (supersedes the per-kind body):

- `## Overview` — the outcome and why (1–3 lines).
- `## Details` — constraints, principles, and the open business decisions
  with where each lands (config / adapter / manual step / launch gate). The
  distillate of domain research; the full reports are **comments** on this
  issue.
- `## Plan` — the sub-issues as `#n` with one line each on what they deliver;
  order comes from blocked-by, not from this list. Later, undecomposed parts
  may stay prose. No `- [ ]` here: the sub-issue panel shows progress.
- `## Acceptance` — the integration checks run after every sub-issue lands
  (`- [ ]`). The parent's exit criterion.

**Sub-issue, or any issue about to be implemented** (the execution unit):

- `## Purpose` — the single goal (1–2 lines).
- `## Requirements` — Draft: provisional; Fixed: confirmed, open decisions
  folded in.
- `## Research` (optional) — the excerpts of the parent's research this issue
  relies on, transcribed so it stays self-contained when the parent closes,
  plus its own kickoff findings. Fold into Requirements when short.
- `## Implementation outline` — Draft: prose bullets of the expected PR
  slices. Fixed: a `- [ ]` checklist of stack layers, bottom to top; tick a
  layer when its PR opens and append the `#n` (the layers land together, so
  the ticks are the progress). The checklist, not a set of issues, is the
  decomposition, so re-slicing is a text edit.
- `## Open decisions` — what kickoff must settle; removed when Fixed, re-added
  when an escalated discovery raises one.
- `## Acceptance` — done checks (`- [ ]`).
- `## Evidence` — links to research comments, decision issues, predecessors.

The body carries no status line: whether the spec is Draft or Fixed shows
in its shape (`<SpecLifecycle>`), and how far the work is shows in the
board's Status, the outline's ticks and the issue's state.

A repository with Issue Forms uses them instead of these skeletons.

</Bodies>

<Notation>

Prefer the forms GitHub renders into links with a title or code; they are
what a reader on github.com sees, in issues, comments, PR bodies and drafts.

| To point at | Write | Why |
| --- | --- | --- |
| An issue or PR in the same repository | `#123` | a short link |
| One in another repository | `owner/repo#123` | short, and names the repository |
| Several related issues | a list, one per line: `- owner/repo#12` | in a list GitHub shows each one's title and state |
| A commit | the short SHA, or `owner/repo@sha` from another repository | a short link |
| Code | a permalink pinned to a commit with its line range: `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L16-L37` (the `y` key on a file view pins it) | a branch link changes under the reader; never `file:line` |
| …in an issue, comment or PR of the same repository | the permalink alone on its line | GitHub shows the code inline |
| …from another repository, or in a draft or a repository file | `[path#L16-L37](permalink)` | it renders as a plain link, so the text must say what it is |
| A message, a sheet, a page, a doc | `[what it is, when](URL)` | never a bare URL |
| A long log or output | `<details><summary>what it is</summary>` around a fenced block | the body stays readable |
| Steps or checks | a task list, `- [ ] …` | progress shows in lists |
| A warning that must not be missed | one `> [!WARNING]` (or `[!NOTE]`) | used everywhere, it stops standing out |
| A person or team | `@name` only to notify them | a mention in an issue or PR notifies; one in a draft does not |

A path on this machine (`/Users/<name>/…`, a worktree) never stands for a
file of the repository: write its repository-relative path or a permalink.

</Notation>

<SpecLifecycle>

An issue that will be implemented has a two-stage spec, and its body's
shape says which stage it is in — no status line repeats it:

1. **Draft** at planning: provisional Requirements, a prose outline, an
   `## Open decisions` section. Deliberate — later issues' PR boundaries
   depend on earlier implementations, so slicing everything up front causes
   rework.
2. **Fixed** at kickoff: run the issue's system research (existing code,
   port sources, library choices, seams), settle Open decisions with the user,
   `gh_issue_update` the body (decisions folded into Requirements, the
   outline turned into a layer checklist, `## Open decisions` removed), then
   implement. The checklist stays editable while the layers above are
   unwritten.

An issue is Draft while it has an `## Open decisions` section or a prose
outline; Fixed once it has neither and its outline is a checklist. Only an
issue derived from an already-confirmed spec starts Fixed. Never implement a
Draft.

</SpecLifecycle>

<Research>

Domain research (market, primary sources, constraints) belongs to the parent
issue as **comments** — the originals — with only the distillate in its
`## Details`. System research (how to realize one issue here) belongs to that
issue's `## Research` at kickoff. Implementation detail is not persisted as
issue content; the PR carries it. Research never gets an issue of its own.

A discovery that exceeds the current scope is not absorbed on the spot:
escalate it to the issue's `## Open decisions` (system level) or a parent
comment (domain level) with `gh_issue_update` / `gh_issue_comment`, and keep
the current PR on scope.

</Research>

<ClosingReferences>

- A PR body carries `Refs #n` while the issue stays open after the merge, and
  `Closes #n` only on the PR whose merge completes it — one of the two, never
  both. Closing keywords fire from any PR into the default branch, so a stack
  writes `Closes` on its top layer only. `git-pullrequest` renders this.
- A **linked development branch** (`gh_issue_develop`) puts its PR among the
  issue's closing references **without any keyword**: the first merge closes
  the issue. Take one only for an issue that is a single PR. A multi-PR issue
  takes plain branches (`git_worktree`, then `git_stack`).
- Parent issues get no branch.

</ClosingReferences>

<Recipes>

- Read before acting: `gh_issue_view { issue }` — it returns the parent, the
  sub-issues, what blocks it, the linked branch, the closing PRs and the board
  item ids, so one call replaces `gh issue view` + `gh pr list` + a board read.
- Create a unit of work under a parent, blocked by a sibling, filed on a
  milestone: `gh_issue_create { title, body, kind, parent: "<n>", blockedBy:
  ["<m>"], milestone: "<title>", createMilestone: true }`. Add
  `addToProject: true` to place it on the board (`gh-projects` says which).
- Create the parent first, then the sub-issues with `parent`; or attach later
  with `gh_issue_relate { issue: "<parent>", addSubIssues: [...] }`.
- Kickoff: `gh_issue_update { issue, body }` with the Fixed body; Status
  In Progress on the board (`gh-projects`).
- Progress note or decision: `gh_issue_comment { issue, body }`; a change to
  the spec edits the body (`appendBody` for an addendum section).
- A layer's PR opened: `gh_issue_update { issue, body }` ticking the outline
  line with its PR `#n`.
- Done: the closing PR merges; or `gh_issue_update { issue, state: "closed",
  reason: "completed", comment }` when no PR closes it. Dropped: `reason:
  "not planned"`. A twin: `reason: "duplicate"` with the original in `comment`.
- Sub-issues of a parent: `gh_issue_list { parent: "<n>", state: "all" }`.
  Open work on a milestone: `gh_issue_list { milestone: "<title>" }`.
- Re-enter in a new session: `gh_issue_view` on the issue; its outline
  checklist and the closing PRs show where it stopped, and `gh stack checkout
  <layer branch or PR>` restores a stack.

</Recipes>

<Supersede>

When issues are split, merged or re-tiered, nothing is deleted and no parent
dangles:

1. Create the successors first, transcribing what they inherit (requirements,
   research excerpts, decisions) so each is self-contained.
2. Comment on each superseded issue with the successor `#n` list and where
   the content went.
3. `gh_issue_relate { issue, removeParent: true }`, then close it —
   `completed` when its job was done (a confirmed spec that was transcribed),
   `not planned` when replaced mid-flight.
4. Re-parent surviving sub-issues onto the successors (`gh_issue_relate {
   issue: "<sub>", parent: "<successor>" }`), splitting any that now spans two.

Closed originals stay readable; successors link back in `## Evidence` or
`**Refs**:`.

</Supersede>

<Guardrails>

- `gh_issue_list` before creating, so a twin is found rather than filed.
- One kind per issue: the tools remove the other `type:*` labels when the
  kind changes.
- A close always carries a reason; the tool refuses one without.
- A write to a repository the viewer does not own succeeds and says
  `foreign: true` — read that before continuing in someone else's tracker.
- Milestones are per repository: a parent whose sub-issues span repositories
  carries the milestone in each, under the same title.
- No `Parent: #n`, no wave numbers, no status percentages in bodies — the
  relations and the panels carry those.

</Guardrails>
