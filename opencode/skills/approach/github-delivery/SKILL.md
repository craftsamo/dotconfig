---
name: approach-github-delivery
description: >-
  Use when work already planned on GitHub is carried to done across sessions:
  kick off a unit (its spec Draft → Fixed, Status In Progress), implement it
  as one native stack of PRs rooted at the default branch, grown one layer at
  a time, tick its outline as each layer's PR opens, land the stack in one
  merge, then close the unit and its parent (着手, Issue を実装する, スタックで
  進める, 再開, kickoff, start the issue, resume the issue, stacked PR, gh stack,
  land the stack). Layers on any approach-* scenario skill. Planning the work
  (the shape, the bodies, filing, changing a plan) is the github-planning
  skill's; opening or updating a PR, even a stack layer, is
  git-pullrequest's. Not for a one-off PR with no issue behind it.
author: CraftSamo
license: MIT
---

<Goal>

Drive a plan that lives on GitHub to done, across sessions, so nothing lives
in a throwaway local TODO or plan file. The plan itself — a parent issue,
its sub-issues as execution units, their order, dates and bodies — is made
and changed with the `github-planning` skill (with `github-issues` and
`github-projects` for the tools). This skill starts where that one stops:
when a unit's work starts.

</Goal>

<WhenToUse>

- Durable, multi-session or multi-step work → plan it on GitHub
  (`github-planning`), then deliver each unit with this skill.
- Within-session steps → the session's todo list (`todowrite`), never an
  issue.
- A companion to any scenario playbook (new-feature, rebuild-migration, …)
  once the work is worth persisting.
- A run Hermes commissions → not this skill's loop: Hermes plans the work on
  GitHub and places the session, and the operating note decides what is
  yours there (`AGENTS.md` `<SessionLocation>`); open PRs with the
  `Closes`/`Refs` it names.

</WhenToUse>

<Units>

Issues stop at the execution unit; below it the unit of work is a PR:

```
Parent issue … the requirement; tracking only, no branch
 └ Unit (sub-issue, or an issue with no parent) … ONE goal that delivers on
    │            its own; one branch or one stack of PRs that lands once
    └ Stack layer … one reviewable PR; NOT an issue — its slice spec lives in
       │            the PR body (Phase N of the session's todo list)
       └ Commit … the steps inside that PR (Phase N.m)
```

A unit's `## Implementation outline` is the decomposition into layers, so
re-slicing is a text edit. A part that must reach the default branch before
the rest is a unit of its own, planned as one.

</Units>

<Kickoff>

A unit is planned as a **Draft**: a prose outline and, usually,
`## Open decisions`. Never implement a Draft. Kickoff turns it **Fixed**:

1. `github_issue_read` `view` the unit and its parent; check that nothing
   that blocks it is still open.
2. Research how to realize it here (existing code, port sources, libraries,
   seams). Post the full findings as a comment and keep in the unit's
   `## Research` only the sourced facts the requirements rest on, copied in
   from the parent's research where it relies on that.
3. Settle every open decision with the user.
4. `github_issue_edit` the whole body: decisions folded into
   `## Requirements`, `## Open decisions` removed, the outline turned into a
   `- [ ]` checklist of stack layers, bottom to top, each line what the layer
   delivers. Comment on what kickoff changed (the `github-planning` rules for
   a changed body apply).
5. Set the unit's Status to In Progress on the board, when it is on one.
6. Branch (`<Branches>`).

The body shows its stage by its shape — an open-decisions section or a prose
outline is Draft, a layer checklist with neither is Fixed — never by a status
line.

</Kickoff>

<Branches>

A unit executes as one **native GitHub stack** (`gh stack`, through
`git_stack` / `git_publish` as `git-pullrequest` `<StackedPRs>` describes)
whose trunk is always the default branch.

- **Parents have no branch**, and units have no merge-vehicle branch: the
  stack's layers land on the default branch directly, together, when the
  unit is done (`<Landing>`).
- **One unit = one stack; one layer = one PR**: `main ← l1 ← l2 ← …`, every
  layer branch named after the unit (`<number>-<slug>/l1`, `/l2`, …).
  Start with `git_worktree { action: "create", branch: "<number>-<slug>/l1" }`;
  after its first commit, `git_stack split` with no cuts makes it the stack's
  bottom.
- **Grow the stack, do not pre-build it.** Add a layer only when about to
  implement it (`git_stack add`, to the top). Inserting or reordering is
  `gh stack modify`, TUI-only; unwritten layers stay outline text.
- **A multi-layer unit takes NO linked development branch.**
  `github_issue_develop` puts the branch among the issue's closing references
  without a keyword, so the first layer to merge would close the unit while
  the layers above are open.
- **A one-PR unit** needs no stack: take `github_issue_develop`, since closing
  on that merge is wanted.

</Branches>

<Layers>

Each layer is opened through `git-pullrequest`; its body is the slice's spec
in that skill's `<BodyStructure>`:

- `Refs #<unit>` on an intermediate layer, `Closes #<unit>` on the
  completing one (normally the top; move it when another layer is appended),
  never both. Closing keywords fire from any PR into the default branch.
- The slice's goal in the summary, `## Out of scope` when a reader would
  expect more, and the done checks with their commands in the verification
  list. No `## Dependencies` (the stack encodes them) and no `## Research`.
- When a layer's PR opens, `github_issue_edit` the unit's outline: tick the
  line and end it `— #<PR>`.
- After changing a lower layer: `git_stack rebase`, `git_publish_preview`,
  `git_publish push`.
- A discovery beyond the unit's scope is not absorbed in the current layer:
  add it to the unit's `## Open decisions` (how to build it) or comment on
  the parent (what to build), and keep the layer on scope. Work the goal
  needs becomes a new unit under the parent, never under the unit
  (`github-planning` "Changing a plan").

</Layers>

<Landing>

A unit's stack lands once, when its goal is done: every layer reviewed and
its checks green. Layers landed one by one leave a half-built goal on the
default branch, and a stack landed under its default message leaves one
commit that names only the top layer.

- **One merge, one message.** A merge commit titled with the unit's goal and
  ` (#<top PR>)`, its body listing every layer bottom-up as
  `- #<n> <PR title>`: the landing plan of `git-pullrequest`
  `<MergeMessageHandoff>`.
- **Hand it over; land only when asked.** Give the landing plan when the
  completing layer is published; the merge runs only on an explicit request.
  A part lands first only when the user says so.
- **After it lands:** the completing layer's `Closes #<unit>` closes the
  unit. Tick each line of its `## Acceptance`; a line it could not meet moves
  to a later unit (that unit's `## Acceptance` gains it, and the line here is
  ticked and ends `— moved to #n`). Then comment `Landed in #<top> (with #a,
  #b):` and what now works, and set Status Done on the board.

</Landing>

<Steps>

1. **Plan** with `github-planning`, once the plan is co-designed: the shape,
   the bodies, filing in dependency order, the board. No branches yet.
2. **Kick off** the next unblocked unit (`<Kickoff>`).
3. **Execute layer by layer** (`<Layers>`), then **land** (`<Landing>`).
4. **Close the loop.** When every unit has landed, run the parent's
   `## Acceptance`, ticking each line, close it (`github_issue_close
   { reason: "completed" }`), set Status Done, and summarize.
5. **Re-enter across sessions.** `github_project_read { method:
   "item_list", status: "-Done,-Cancelled" }` → `github_issue_read` `view`
   the unit: its outline checklist and closing PRs say where it stopped;
   `gh stack checkout <layer branch or PR>` restores the stack and
   `gh stack view` shows what landed.

In a run Hermes commissions, its operating note decides which of these
GitHub writes are yours.

</Steps>

<AntiPatterns>

- Slicing every unit into PRs up front — later boundaries depend on earlier
  implementations; slice at kickoff, into outline text.
- Opening the whole stack as draft PRs before implementing — empty layers
  cannot be PRs, and mid-stack insertion is TUI-only afterwards.
- An issue per stack layer — the PR body is its spec.
- A linked development branch on a multi-layer unit, a parent branch, or a
  merge-vehicle branch.
- Landing a unit layer by layer unless the user asks, or under the top
  layer's default message.
- Implementing a Draft, or absorbing an out-of-scope discovery mid-layer.
- Leaving the plan or its progress in a local TODO, plan or notes file.

</AntiPatterns>

<Gates>

- [ ] The unit is Fixed before its first layer: a layer checklist, no open
  decisions, Status In Progress.
- [ ] Trunk is the default branch; layers named after the unit and appended
  as implemented; no linked development branch on a multi-layer unit.
- [ ] Exactly one layer carries `Closes #<unit>`; the others `Refs #<unit>`.
- [ ] The outline is ticked with each layer's PR as it opens.
- [ ] The stack lands once, as one merge commit whose message names the goal
  and lists every layer; acceptance ticked or moved, Landing comment posted.
- [ ] Re-enterable from the board and `github_issue_read` alone.

</Gates>
