---
name: approach-github-planning
description: >-
  Use when a co-designed plan should live on GitHub and be driven to done
  across sessions — decompose a requirement into a parent issue whose
  sub-issues are the execution units (one branch or one native stack of PRs
  each, spec Draft → Fixed at kickoff), order them with blocked-by, file them
  on a milestone, show them on a board, then execute each as a stack of PRs
  rooted at the default branch, grown one layer at a time (計画を Issue に,
  起票して進める, 親 Issue と sub-issue, ロードマップに載せる, plan on GitHub,
  track work, parent issue, sub-issues, milestone, stacked PR, gh stack,
  development branch). Layers on any approach-* scenario skill; delegates
  issue mechanics and bodies to gh-issues, boards to gh-projects and PRs to
  git-pullrequest (opening or updating a PR, even a stack layer, is
  git-pullrequest's). Use ONLY to orchestrate planning ↔ GitHub, not for the
  mechanics themselves.
author: CraftSamo
license: MIT
---

<Goal>

Persist a co-designed plan on GitHub and drive it to done across sessions,
so nothing lives in throwaway local TODO / plan files. Once a plan is
co-designed (investigate → confirm the goal → co-design → small reversible
steps), decompose the requirement into a parent issue whose sub-issues are
the execution units, defer PR-level slicing to each sub-issue's kickoff, and
execute each as a native GitHub stack of PRs rooted at the default branch.
Delegate issue mechanics and bodies to `gh-issues`, boards to `gh-projects`
and PR creation to `git-pullrequest`.

</Goal>

<WhenToUse>

- Durable, multi-session or multi-step work → record and track it on GitHub.
- Within-session steps → the session's todo list (`todowrite`), never an issue.
- A companion to any scenario playbook (new-feature, rebuild-migration, …)
  once the work is worth persisting.

</WhenToUse>

<Hierarchy>

Issues stop at the execution unit; below it the unit of work is a PR:

```
Board item … the parent issue (and standalone issues); sub-issues when their
             dates or Status matter on their own (gh-projects)
Parent issue … the requirement; tracking only, no branch
 └ Sub-issue … ONE goal that delivers on its own, the execution unit
    │           ("do this now"); one branch or one stack of 1–3 PRs;
    │           carries its spec (Draft → Fixed) and implementation outline;
    │           ordered among siblings with blocked-by
    └ Stack layer … one reviewable PR in the sub-issue's native stack;
       │            NOT an issue — its slice spec lives in the PR body
       │            (Phase N of the session's todo list)
       └ Commit … the steps inside that PR (Phase N.m)
```

There is deliberately no issue below the execution unit: an issue and its
PR carried the same Scope / Acceptance twice, and the PR is the better home
(diff, checks and review beside the spec). The unit's `## Implementation
outline` is a plain checklist of planned layers, so re-slicing costs a text
edit, not issue surgery.

Shape (decompose along the codebase's structural seams):

- One sub-goal that fits one PR, no wider context → a **single issue**.
- One unit-sized sub-goal (1–3 PRs) → a **single issue** with the unit body.
- Several unit-sized sub-goals → a **parent issue** with sub-issues.
- A parent that would decompose straight into ~5+ PR-sized pieces, or spans
  several domains, is missing a tier: insert sub-issues that are goals. A
  unit is the smallest thing that delivers a meaningful outcome on its own
  and fits one branch or one stack of a few PRs; anything larger is still a
  parent-sized lump — keep decomposing.
- A feature that must land atomically is one unit (its stack merges
  atomically), never a parent (a parent has no branch or stack).

Time and order live in GitHub's relations, not in text: a **milestone** on
the parent (and on sub-issues with their own date), **blocked by** on a
sub-issue that must wait for a sibling. The parent's `## Plan` lists the
sub-issues with one line each; it does not number waves. Bodies: `gh-issues`
`<Bodies>`.

</Hierarchy>

<ResearchModel>

Each tier investigates different questions, at different times, recorded in
different places. Research never gets an issue of its own.

| Tier | Research | Question | When | Recorded where |
| --- | --- | --- | --- | --- |
| Parent | Domain: market, competitors, primary sources, business constraints | What should we build? | Around creation | Parent **comments** hold the full reports; the body's `## Details` holds the distilled constraints, principles and open business decisions |
| Sub-issue | System: existing code, port sources, library / provider comparison, seams | How do we realize this here? | At **kickoff** (the Draft → Fixed gate) | The sub-issue's `## Research`: the parent-research excerpts it depends on, transcribed, plus its own findings; conclusions resolve `## Open decisions` into `## Requirements` |
| Layer | Implementation detail: files, conventions, API shapes, how to test | Where and how do we change it? | Inline | Not persisted as issue content; the PR body's Scope and the diff are the record |

Down: parent research → each sub-issue transcribes what it relies on. Up: a
discovery that exceeds the current scope is escalated to the sub-issue's
`## Open decisions` (system) or a parent comment (domain), never absorbed on
the spot (`gh-issues` `<Research>`).

</ResearchModel>

<BranchTopology>

A unit executes as one **native GitHub stack** (`gh stack`, through
`git_stack` / `git_publish` as `git-pullrequest` `<StackedPRs>` describes)
whose trunk is always the default branch.

- **Parents have no branch.** A months-long parent branch would starve the
  default branch and rot; the parent's progress is its sub-issue bar.
- **Units have no merge-vehicle branch either.** Layers land on the default
  branch one by one, so it never falls a unit behind.
- **One unit = one stack; one layer = one PR**: `main ← l1 ← l2 ← …`, every
  layer branch named after the unit (`<number>-<slug>/l1`, `/l2`, …).
- **A multi-layer unit takes NO linked development branch.**
  `gh_issue_develop` registers the branch among the issue's closing
  references without a keyword, so the first layer to merge closes the unit
  while the layers above are open. Use plain branches (`git_worktree`).
- **Grow the stack, do not pre-build it.** Add a layer only when about to
  implement it (`git_stack add`, to the top). Inserting or reordering is
  `gh stack modify`, TUI-only; unwritten layers stay outline text.
- **The trunk is the default branch, always.** A non-default trunk
  (`gh stack init --base`; `git_stack` refuses it) breaks closing keywords
  and makes two kinds of PR.
- **Closing.** Intermediate layers carry `Refs #<unit>`; the completing
  layer carries `Closes #<unit>` instead (normally the top; move it when
  another layer is appended). Fill the unit's `## Evidence` before that
  layer merges.
- **Degenerate case**: a one-PR unit needs no stack, and `gh_issue_develop`
  is right there — closing on that merge is wanted.

</BranchTopology>

<StackLayerPR>

A layer's PR body is the slice's spec (the old work sub-issue's content
lives here); `git-pullrequest` renders it against the repository's own PR
convention and template:

- `## Purpose` — one line, with `Refs #<unit>` on an intermediate layer or
  `Closes #<unit>` on the completing one (never both).
- `## Scope` — what the layer includes; `## Out of scope` when a reader
  would otherwise expect more.
- `## Acceptance` — done checks, including the verification commands.
- No `## Dependencies` (the layer below is the dependency and the stack
  encodes it) and no `## Research` (findings stay in the PR discussion;
  out-of-scope ones escalate to the unit's `## Open decisions`).

</StackLayerPR>

<Steps>

1. **Capture.** A new requirement or idea → a draft on the board
   (`gh_project_item_add`) or, with a repository known, an issue
   (`gh_issue_create { kind, milestone }`). Safe before committing to it.
2. **Decompose (when aligning on the plan).** Split along the codebase's
   seams into unit-sized sub-goals (`<Hierarchy>`). Record domain research
   as parent comments; write the parent body (`## Details`, `## Plan`,
   `## Acceptance`) and each sub-issue's Draft body per `gh-issues`.
3. **Gate — file + wire.** When decided: promote the draft
   (`gh_project_item_promote`) or create the parent; create the sub-issues
   in dependency order with `gh_issue_create { parent, blockedBy, milestone,
   kind }` so `#n` references are real; put the parent on the board
   (`addToProject: true`), sub-issues too when their dates matter. No
   branches yet.
4. **Kickoff a unit (repeat).** Pick the next unblocked sub-issue: run its
   system research → settle `## Open decisions` with the user →
   `gh_issue_update` the body to Fixed with the outline as a layer
   checklist and `**Implementation status**: In progress`; Status → In
   Progress on the board. Then a task branch `<number>-<slug>/l1` off the
   default branch (`git_worktree { action: "create" }`); after its first
   commit, `git_stack split` with no cuts makes it the stack's bottom. A
   one-PR unit takes `gh_issue_develop` instead.
5. **Execute layer by layer.** Implement the current layer, PR it via
   `git-pullrequest` (`Refs #<unit>`; `Closes` on the completing layer),
   then `git_stack add` for the next. Tick the outline as layers land
   (`gh_issue_update`). After changing a lower layer: `git_stack rebase`,
   `git_publish_preview`, `git_publish push`. Land only on an explicit
   request with `gh stack merge` (atomic); the top layer's merge closes
   the unit.
6. **Close the loop.** When every sub-issue lands, run the parent's
   `## Acceptance`, close it (`gh_issue_update { state: "closed", reason:
   "completed" }`), set Status Done, summarize. No orphan local files.
7. **Re-enter across sessions.** `gh_project_item_list { status:
   "-Done,-Cancelled" }` → `gh_issue_view` the unit: its header, outline checklist
   and closing PRs say where it stopped; `gh stack checkout <layer branch
   or PR>` restores the stack and `gh stack view` shows what landed.

</Steps>

<Supersede>

Splitting, merging or re-tiering issues follows `gh-issues` `<Supersede>`:
successors first (self-contained), a comment on each superseded issue,
unparent and close with the right reason, re-parent the survivors. Nothing
is deleted; no parent dangles.

</Supersede>

<AntiPatterns>

- Do not slice every unit into PRs up front — later PR boundaries depend on
  earlier implementations; slice at kickoff, into outline text.
- Do not open the whole stack as draft PRs before implementing — empty
  layers cannot be PRs, placeholder commits and their CI are waste, and
  mid-stack insertion is TUI-only afterwards.
- Do not file an issue per stack layer — the PR body is its spec.
- Do not take a linked development branch for a multi-layer unit — the
  first merge closes it.
- Do not create a parent branch or a unit merge-vehicle branch.
- Do not number waves or write `Parent: #n` in bodies — blocked-by and the
  sub-issue panel carry order and parentage.
- Do not create research-only issues — domain research is parent comments,
  system research is the consuming sub-issue's `## Research`.
- Do not implement a Draft — Fixed gates the slicing.
- Do not absorb out-of-scope discoveries mid-implementation — escalate.
- Do not leave the plan in a local TODO / plan / notes file.

</AntiPatterns>

<Gates>

- [ ] Shape chosen by decomposition: 1 PR → an issue; 1–3 PRs → an issue
  with the unit body; several units → a parent with sub-issues; a parent
  never decomposes straight into PRs.
- [ ] Order and time are relations: blocked-by between siblings, milestone
  on the parent; the parent's `## Plan` lists `#n` with no checkboxes.
- [ ] Every unit body carries its spec status; Draft has Open decisions,
  Fixed has a layer checklist.
- [ ] Research tiered: parent comments / unit `## Research` (transcribed) /
  none at layer tier.
- [ ] Branches: trunk is the default branch, layers named after the unit and
  appended as implemented; no parent branch, no merge vehicle, no linked
  development branch on a multi-layer unit.
- [ ] Exactly one layer carries `Closes #<unit>`; the others `Refs #<unit>`.
- [ ] Superseded issues closed with successor links, never deleted.
- [ ] Re-enterable from the board and `gh_issue_view` alone.

</Gates>
