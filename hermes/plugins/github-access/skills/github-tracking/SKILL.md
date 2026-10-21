---
name: github-tracking
description: "Use to change GitHub Issues and Projects boards for the user: setting up a board (standard fields and views, a repository link, a Waiting status), capturing work as drafts, noting progress, moving Status, turning a draft into an issue, creating and relating issues (parent, sub-issues, blocked-by, milestone), commenting and closing. Covers proposing to track work on GitHub, batching changes onto one approval card, and what each tier (own / shared / other) needs before a write."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [github, issues, projects, board, tracking, draft, approval]
    category: technic
---

# Changing Issues and boards through `github_change`

Reading, the board model and when a draft becomes an issue:
`skill_view(name="github-access:github")`. This skill is how a change gets
made.

## Contract

- **Only the tool.** Every change goes through `github_change`. The terminal
  path (`gh issue …`, `gh project …`, `gh api`) is blocked.
- **Tracking is the user's choice.** Put work on GitHub when the user asked
  for it, or after proposing it and hearing yes. Size, length or a job's
  type never decides it alone. Propose it only for a roadmap of several
  Phases or a hand-over to other people, once per job: one sentence naming
  the board (and the repository, if issues) it would go on. Operational work
  around a repository the job touches (its hosting, DNS, domain, a contract, a
  hand-over item) belongs to that job and goes on the same board as drafts;
  other work goes on GitHub only when the user asks.
- **One card per list.** Gather the changes of one step into one
  `github_change` call: the card shows each target with its tier and one line
  per change. A list that fits a mandate in force runs without one; the
  wording agreement below still applies, since a mandate skips the card,
  not the conversation. A denial or a timeout means nothing changed: never send the
  same list again unchanged; ask what to change.
- **Read before writing.** Read the board or the issue fresh, then build the
  list from what is there now: an item id from `github_board` `items` or
  `github_issue` `view`, an option name from `github_board` `resolve`.
- **The list stops at the first failure.** The result says what was done,
  what failed (`partial`: what of that change already exists, such as the
  issue it created) and what was not tried. Report it as it is; fix the
  cause, then send only what is still missing. A failure marked `uncertain`
  may have happened after GitHub acted: read the board or issue before
  sending anything again, never resend blind.
- **A changed target asks again.** When a board or repository changed since
  the card (another board resolves, a repository went public), the write is
  refused: read again and send the list again for a new card.
- **Mentions notify.** An `@name` in an issue's title or body notifies that
  person or team, so such an edit counts as a new message, not a routine
  update.

## Before writing, by tier

| Tier | Before the call |
| --- | --- |
| `own` | nothing beyond the card |
| `shared` | agree the exact words of anything others will read (an issue's title and body, a comment, a close comment): write them to a Markdown file in the job directory and ask with `clarify`, the file as `MEDIA:` in its `context` and a few lines of summary in the question; then send exactly those words |
| `other` | the same, and say first that it is someone else's tracker and who will be notified |

The file arrives before the question card; one put in the reply of the turn
that sends the change would arrive after the approval card, so it never goes
there. For a roadmap, one file holds the parent and every sub-issue.

What a body may link to, and what it may say about other people and private
sources, is in the read skill's "Background". Never write a secret value or a
key's location on any tier: a board can be made public later.

The tool checks every text a change writes before any card (field values,
a kind, a milestone and label names included, and a promoted draft's own
words):

- something that looks like a token or a private key is refused, on every
  tier;
- on a target others can read, a path of this machine is refused with how to
  write it: a home path as `~/…`, a file of a repository as its
  repository-relative path or a permalink, a working or private path (the
  workspace, a job directory, the private configuration) in words. Rewrite
  and send again; on the user's own private targets paths go as they are,
  which keeps a debugging note whole;
- the card lists the sites each change links to, the local paths it carries,
  and code links that follow a branch.

## Writing for GitHub

GitHub renders some forms as links with their title or code; prefer them.

| To point at | Write | Why |
| --- | --- | --- |
| An issue or PR in the same repository | `#123` | a short link |
| One in another repository | `owner/repo#123` | short, and names the repository |
| Several related issues | a list, one per line: `- owner/repo#12` | in a list GitHub shows each one's title and state |
| A commit | the short SHA, or `owner/repo@sha` from another repository | a short link |
| Code | a permalink pinned to a commit with its line range, `https://github.com/o/r/blob/<sha>/path#L10-L20` | a branch link changes under the reader |
| …in an issue or comment of the same repository | the permalink alone on its line | GitHub shows the code inline |
| …from another repository, or in a draft | `[path#L10-L20](permalink)` | it renders as a plain link, so the text must say what it is |
| A message, a sheet, a page | `[what it is, when](URL)` | never a bare URL |
| A long log or output | `<details><summary>what it is</summary>` with a fenced block inside | the body stays readable |
| Steps | a task list, `- [ ] …` | progress shows in lists |
| A warning that must not be missed | one `> [!WARNING]` (or `[!NOTE]`) | used everywhere, it stops standing out |
| A person or team | `@name` only to notify them | a mention in an issue notifies; one in a draft does not |

## Setting up a board

When `github_board` `resolve` finds no board on any route, the tracking you
propose includes making one: name its owner and title in the same sentence
(the organization for a repository the team shares, else the user's own,
titled `Roadmap`), and make it only after the user agrees.

- **Make it:** `board_create` with `owner` (`"@me"` or the organization),
  `title` (default `Roadmap`) and `link_repo` (the repository, so its board
  resolves first). It brings Status (Todo / In Progress / Done / Cancelled),
  Start and Target, and the Kanban, Backlog and Roadmap views. A board of
  that title the owner already has is reused and topped up, never made
  twice. `template` copies a board the user keeps configured, views and all.
- **Tell the user once** that a new board's Roadmap view draws no bars until
  Start and Target are bound to it in GitHub's own page, and that grouping
  and sort are set there too: the API does not take them.
- **A board without `Waiting`:** `field_ensure` with `name: "Status"`,
  `data_type: "SINGLE_SELECT"`, `options: ["Waiting:ORANGE"]`; existing
  options and every item's value stay as they are.
- **Another field or view:** `field_ensure` (an `Area` or `Priority`
  single-select, a date) and `view_ensure` (a layout, a filter such as
  `-status:Done`, the columns by field name). Kind is never a board field: it
  is the issue's type or `type:*` label.
- **Link an existing board** to a repository: `board_link` with `repo`
  (`unlink: true` undoes it).

Changes on a board made in the same list cannot follow its creation: the
list resolves its board before anything runs. Make the board in one call and
put items on it in the next.

## Recipes

- **Capture** (an idea, a hand-over item, work with no repository yet):
  `draft_add` with `title` (an action phrase), `body` (why, where it came
  from as links, "Together with: …", "After: …") and `fields`
  (`{"Status": "Todo"}`; `Target` as `YYYY-MM-DD` when there is a date).
  Several at once go in one list.
- **Progress on a draft:** `draft_note` with a dated line ("2026-10-21:
  confirmed the address; waiting on the signer"). Waiting on someone outside:
  `item_set` `Status` to `Waiting` when the board has it (else add it as
  "Setting up a board" says).
- **Done without an issue:** `draft_note` with what proves it done, then
  `item_set` `Status` `Done`.
- **Becomes an issue** (the conditions are in the read skill):
  `draft_promote` with `repo`, `kind` and the milestone; then `issue_edit`
  with the issue form body (purpose, requirements, acceptance; the draft's
  notes under `## Evidence`) and `issue_relate` for its parent and
  blocked-by. A later call, since the promote returns the issue's number.
- **New issue straight away:** `issue_create` with `kind`, `parent`,
  `blocked_by`, `milestone` (`create_milestone` when it is new) and
  `board_fields` to place it on the board in the same change.
- **A goal with pieces:** one list: the parent first, then an
  `issue_create` per piece with `parent: "$1"` and `blocked_by` the piece
  before it (`"$2"`). `$N` is the issue change N of the same list creates;
  only `issue_create`'s `parent` and `blocked_by` take it, and the card reads
  it as "change N's issue".
- **Work moves:** `item_set` `Status` `In Progress` / `Done`; tick a step
  with `issue_edit` `body` (read it, change the checkbox, send it whole) or
  add one with `append_body`.
- **Close:** `issue_close` with a reason (`completed`, `not planned`,
  `duplicate`) and a `comment` saying why; when a PR's merge already closed
  it, only move the board's Status. Closing an issue does not move Status.
- **Tidy:** `item_archive` for a dropped draft or a long-closed item; nothing
  is ever deleted.

## Mandates

A mandate lets a bounded kind of change skip its card. Propose one when
tracking is agreed for work that will update GitHub often (a build ticking
steps, Status moving through a week): one sentence naming the boards and
repositories, the classes, and how many days (the work's expected end, at
most 30). Never propose one to get past a card the user just denied.

- `routine` (fields, notes, archiving, an issue's own words without a new
  mention) is the usual class. Add `create` only for the user's own private
  board and repositories, and only when they want new items and comments
  there to run without a card too.
- Whatever the terms, a target someone else owns always asks, and one others
  can read takes routine changes only. A card that still appears names why.
- `github_mandate` `list` before relying on one; `revoke` it when the work is
  done or the user asks. A mandate ends on its own at its last day.
- A list inside a mandate also runs where nobody is present (a cron job), so
  a scheduled job that updates GitHub needs one, and only for what it does.

## Replacing issues

Splitting, merging or re-tiering issues: create the successors first
(each self-contained), comment on each replaced issue with the successor
numbers, remove its parent (`issue_relate` `remove_parent`) and close it
(`completed` if its job was done, `not planned` if replaced mid-flight), then
move the surviving sub-issues to their new parent.
