---
name: manage-tracking
description: "Use to change GitHub Issues and Projects boards for the user: setting up a board, drafts, Status, issues and how they relate, comments, closing, or filing a job's plan on GitHub. Reading is github-access:read-tracking."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [github, issues, projects, board, tracking, draft, approval]
---

# Changing Issues and boards through `github_change`

Reading, the board model and when a draft becomes an issue:
`skill_view(name="github-access:read-tracking")`. This skill is how a change gets
made.

## Contract

- **Only the tool.** Every change goes through `github_change`. The terminal
  path (`gh issue …`, `gh project …`, `gh api`) is blocked.
- **A repository job is recorded; other work when asked.** Work that
  changes a repository goes on GitHub as its plan is approved: each
  execution unit an issue, Fixed before it is built, on the board that
  resolves for the repository (the engineering entries say when). The user
  excludes a job in their own words, and then nothing of it is written;
  size, length or a job's type never excludes it alone. Operational work
  around a repository the job touches (its hosting, DNS, domain, a contract, a
  hand-over item) belongs to that job and goes on the same board as drafts;
  work outside any repository goes on GitHub only when the user asks.
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
| One in another repository, or any issue from a draft | `owner/repo#123` | short, and names the repository; a draft has none, so `#123` there is plain text |
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

## Issue bodies

The shapes of the read skill's "Parent and execution unit", in GitHub
Markdown: `##` for the sections, `**Label**:` for a one-line field, only the
sections that apply, never an empty placeholder. Section names go in the
repository's language with the same meaning; a repository with Issue Forms
uses their headings instead. Title: an action phrase (EN imperative,
JA「〜する」), the detail in the body.

**Parent** (a goal with pieces):

- `## Overview` — the outcome and why, 1–3 lines.
- `## Details` — constraints, principles, the open business decisions and
  where each lands. The distillate of what was found out; the full reports
  are comments on the parent.
- `## Plan` — the sub-issues as `#n` with one line each on what they
  deliver; no checkboxes (the sub-issue panel shows progress), no numbering
  (blocked-by carries the order). Parts not yet split may stay prose.
- `## Acceptance` — the checks run after every piece lands (`- [ ]`).

**Execution unit** (a sub-issue, or an issue about to be implemented):

- `## Purpose` — the single goal, 1–2 lines.
- `## Requirements` — Draft: provisional. Fixed: confirmed, the open
  decisions folded in.
- `## Research` (optional) — what of the parent's findings this unit rests
  on, transcribed so it stands alone when the parent closes, plus what
  kickoff found.
- `## Implementation outline` — Draft: prose bullets of the expected
  slices. Fixed: a `- [ ]` checklist of PR layers, bottom to top; a line is
  ticked with its `#n` when that PR opens.
- `## Open decisions` — what kickoff must settle; removed when Fixed.
- `## Acceptance` — done checks (`- [ ]`).
- `## Evidence` — links to the comments, decisions and predecessors.

No status line: the shape says Draft or Fixed, the board's Status and the
ticks say how far.

**Any other issue** (one that is not a unit of a plan), by kind: feature
`## Purpose` / `## Requirements` / `## Acceptance criteria`; enhancement
`## Problem` / `## Change` / `## Impact`; bug `## Symptom` /
`## Suspected cause` / `## Repro steps`; chore `## Summary` and
`**Target**:`; design `## Goal / context` / `## Options` / `## Decision`;
test `## Target` / `## Cases` / `## Pass criteria`.

## Setting up a board

When `github_board` `resolve` finds no board on any route, the plan you put
to the user includes making one: name its owner and title in the same
sentence (the organization for a repository the team shares, else the user's
own, titled `Roadmap`), and make it only after the user agrees.

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
  with the body in its shape ("Issue bodies"; the draft's notes under
  `## Evidence`) and `issue_relate` for its parent and blocked-by. A later
  call, since the promote returns the issue's number.
- **New issue straight away:** `issue_create` with `kind`, `parent`,
  `blocked_by`, `milestone` (`create_milestone` when it is new) and
  `board_fields` to place it on the board in the same change (`Status`;
  `Target` as `YYYY-MM-DD` when there is a day).
- **A goal with pieces:** one list: the parent first (its body, the
  milestone that holds its date), then an `issue_create` per piece with
  `parent: "$1"`, `blocked_by` the piece before it (`"$2"`) and the
  execution-unit body at Draft. `$N` is the issue change N of the same list
  creates; only `issue_create`'s `parent` and `blocked_by` take it, and the
  card reads it as "change N's issue". The parent's `## Plan` names the
  pieces by their numbers, so it is filled by an `issue_edit` in the next
  call. Milestones are one per date, not one per piece: a piece gets its
  own only when its date differs from the parent's.
- **Kickoff of a unit:** the next piece nothing blocks. Read it, then a
  plan run through OpenCode (`skill_view(name="opencode:drive")`) reads
  the code and proposes what Fixed needs: the open decisions resolved, the
  outline as layers. Settle the decisions with the user (on a `shared` or
  `other` target, agree the words as "Before writing" says), then
  `issue_edit` the whole body to Fixed (the outline a checklist, the open
  decisions gone) and `item_set` `Status` `In Progress`; the first unit
  under a parent moves the parent to `In Progress` in the same list. Only
  then a build. OpenCode never writes the issue's plan: a plan proposes the
  body, a build reads it and reports a slice that will not fit as a
  question; under the mandate ("Mandates") a build ticks its own layers.
- **Work moves:** tick an outline line with its PR `#n` by `issue_edit`
  `body` (read it, change the checkbox, send it whole) or add a step with
  `append_body`; a decision or a hand-over is an `issue_comment`. When the
  unit's last PR lands, `item_set` `Status` `Done`. When the parent's last
  unit is Done, its acceptance is checked, it is closed and set `Done` too.
- **Waiting on someone outside:** a dated `issue_comment` on the parent and
  `item_set` `Status` `Waiting`; when it resumes, another dated comment and
  back to `In Progress`.
- **Close:** `issue_close` with a reason (`completed`, `not planned`,
  `duplicate`) and a `comment` saying why; when a PR's merge already closed
  it, only move the board's Status. Closing an issue does not move Status.
- **Tidy:** `item_archive` for a dropped draft or a long-closed item; nothing
  is ever deleted.

## Mandates

A mandate lets a bounded kind of change skip its card. Propose one when a
job's plan is filed and the work will update GitHub often (layers ticked as
their PRs open, Status moving through a week): one sentence naming the boards and
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
- An OpenCode build given the mandate's id writes its own issue's state under
  it (a ticked layer, its Status to In Progress), each write checked against
  the mandate as it happens; the engineering entries say when to pass it.

## Replacing issues

Splitting, merging or re-tiering issues: create the successors first
(each self-contained), comment on each replaced issue with the successor
numbers, remove its parent (`issue_relate` `remove_parent`) and close it
(`completed` if its job was done, `not planned` if replaced mid-flight), then
move the surviving sub-issues to their new parent.
