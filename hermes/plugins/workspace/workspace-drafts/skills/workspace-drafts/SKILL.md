---
name: workspace-drafts
description: Use when the Assistant inventories existing workspace drafts or incoming inbox items with workspace_drafts, checks for a draft before starting a job, filters stale or misnamed entries, or interprets legacy, partial or truncated results. Read-only and metadata-only. Not for reading draft contents as canon, creating or moving files, promoting or deleting drafts, choosing the shared workspace layout, or handling inbound A2A requests.
---

# Workspace draft inventory

Use `workspace_drafts` to inspect draft and inbox metadata. This plugin-owned
skill is registered for the Assistant as `workspace-drafts:workspace-drafts`.
Use the tool schema for arguments; do not replace the tool with a terminal
`ws-drafts` invocation or a filesystem scan.

## Boundaries

- This is a **read-only, metadata-only** inventory: names, sizes, file counts
  and modification times. The reader does not open file contents or traverse
  symlink targets, and does not create, move or delete files.
- Shared placement, draft/canon status, promotion and deletion rules belong
  to the Assistant pipeline's
  [workspace layout reference](~/.hermes/profiles/assistant/skills/assistant-pipeline/references/workspace-layout.md).
  Read that reference for file handling and approval decisions; this skill
  does not execute those operations or grant their permission.
- Do not call the tool for an inbound A2A request. It refuses those requests;
  do not bypass the refusal through another tool, command or filesystem scan.
- Names, paths and diagnostics can reveal sensitive work. Query only the
  requested scope and summarize counts, age, flags and uncertainty. Never
  paste raw inventories, unrelated Group names, absolute paths or diagnostic
  exception text into chat or logs. External sharing needs specific user
  approval.

## Choose the inventory

Take the user's requested scope and purpose as input: a draft for the current
job, an overview, flagged drafts, or incoming material. Keep drafts and inbox
items separate when interpreting counts.

| Need | Action and result |
| --- | --- |
| Overview of drafts | `summary`: `groups` and draft `totals` |
| Inspect possible drafts for a job or flagged entries | `list`: `drafts`, matching `totals` and `truncated` |
| Inspect incoming items waiting for triage | `inbox`: `items`, `sources`, matching `totals` and `truncated` |

1. Prefer a known Group for a job-specific lookup. Set `group` to its full
   Group key when possible. Matching is case-insensitive and tries exact
   names, then prefixes, then substrings; one query may select several Groups.
   Check returned Group keys before claiming the result is about one Group.
   Ask for clarification if the intended Group remains uncertain. `root` or
   `(unassigned)` selects unassigned work, not every Group.
2. Use `summary` for an overview and `list` for individual draft metadata.
   A summary without `group` also reports an `inbox` block. Its inbox counts
   are separate: draft `layout` and `flags` filters do not filter that block.
   Use the `inbox` action when filtering inbox items.
3. Before a new job, use the inventory to identify possible existing work in
   the requested scope. Metadata alone does not establish that an entry is
   the same job or that its contents are correct. Hand any unresolved match
   back to the pipeline; do not open, resume or modify files from this skill.

## Narrow and sort results

- Draft `layout` is `current`, `legacy` or `all` (default). The plugin reports
  what it finds; interpretation of retired locations remains in the common
  layout reference.
- Send `flags` as an array. Every requested flag must match (**AND**, not OR):
  - `stale`: a draft's newest file modification is at least `stale_days` old
    (default 14). For an empty directory, its directory modification time is
    used. This measures inactivity, not the start date encoded in its name.
  - `misnamed`: a current-layout entry's name cannot be parsed by the reader's
    naming check. Consult the common layout rule; do not rename it here.
  - `legacy`: an entry was found in the earlier layout. These entries are
    classified separately from `misnamed`; neither flag authorizes cleanup.
- For draft `list`, `sort` is `idle` (default, most idle first), `size`
  (largest first), `name`, or `started` (ascending parsed start, with unparsed
  names first).
- `limit` applies to `list` and `inbox`: default 200, range 1..1000. Both
  stale thresholds accept integer days in 1..3650. Change a threshold only
  to answer the requested question; it changes this query, not stored policy.
- `summary` is an aggregate, not a limited row list. Use `list` when individual
  rows, sorting or a limit are needed.

## Inspect the inbox

Call `inbox` without `group`, without a non-default `layout`, and with no flags
or just `flags=["stale"]`. Other draft flags do not apply. Inbox sort choices
are `idle`, `size` and `name`; `started` is not supported.

For inbox items, `stale` and `sort=idle` use the **oldest** file's waiting age
(`age_days`), not the newest file's idle time. The threshold is
`inbox_stale_days` (default 7). Adding a newer file does not hide an older
waiting item. Use the returned `sources` aggregates for a concise overview;
do not interpret source labels as permission to contact or upload elsewhere.

## Interpret coverage and failures

1. Check for a top-level `error` before using results. The tool does not return
   an `ok` success bit. Invalid arguments or a missing workspace root are
   failures, not empty inventories; summarize the failure category without
   copying paths or candidate Group lists from the error.
2. Check `status`: `complete` means the reader reported no partial-scan
   diagnostics; **`status=partial`** means some metadata could not be read.
   Inspect `diagnostics` locally and report the uncertainty. Do not turn a
   partial or empty result into a claim that no work exists.
3. Check `truncated` for `list` and `inbox` independently of `status`. If true,
   only the first `limit` rows are returned; `totals` describe all matching
   entries measured by that scan. Narrow the request or raise `limit` within
   its allowed range. There is no offset/pagination argument; do not invent
   one or claim to have inspected rows that were not returned.
4. A result without entries means none were found in that query's scope and
   coverage. It is not authorization to create a replacement or remove files.
5. An unknown Group is a clarification point. Do not silently fall back to a
   workspace-wide inventory, expose all suggested Groups or create a Group
   to make the query succeed. A conflicting or unreadable location also does
   not authorize filesystem repair.

The user-facing `/drafts` command directly invokes the same reader. With no
argument it shows a summary; `inbox` shows incoming items, `stale`, `misnamed`
or `legacy` selects flagged drafts, and other text selects a Group. Interpret
its output with the same coverage limits; the command does not load this
skill or perform file changes.

## Completion

Return a scoped metadata summary with any partial/truncated coverage stated.
Identify possible existing work or items needing a decision, without claiming
their contents were reviewed. Route any proposed file handling back to the
pipeline and its common rules. Stop after the inventory: no automatic
promotion, deletion, renaming, relocation, upload or external send.
