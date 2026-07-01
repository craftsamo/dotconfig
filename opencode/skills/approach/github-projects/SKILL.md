---
name: approach-github-projects
description: >-
  Use when durable, multi-step, or cross-session work from an approach should
  live on GitHub Projects — decompose a high-level requirement into an epic
  with phased sub-issues (or a single issue) and drive it to done through
  linked development branches and stacked PRs (ロードマップ, 計画をボードに,
  エピック, Parent issue, Sub-issue, 起票して進める, track work, roadmap, epic,
  stacked PR, development branch). Applies on top of the `approach` spine;
  delegates board mechanics to `manage-github-projects` and PR creation to
  `git-pullrequest`. Use ONLY to orchestrate planning ↔ GitHub Projects, not
  for board mechanics themselves.
---

<Goal>

Persist a co-designed plan on GitHub Projects and drive it to done across
sessions, so nothing lives in throwaway local TODO/plan files. Apply on top of
the `approach` spine (investigate → confirm the goal → co-design → small
reversible steps): decompose the requirement, materialize it as a single issue
or an epic with sub-issues, and wire each into a linked development branch and
stacked PR. Delegate board operations to `manage-github-projects` and PR
creation to `git-pullrequest`.

</Goal>

<WhenToUse>

- Durable / multi-session / multi-step work → record and track it on the board.
- Ephemeral within-session steps → keep using TodoWrite, not the board.
- Cross-cutting companion: layer it on any scenario playbook (new-feature,
  rebuild-migration, …) once the work is worth persisting.

</WhenToUse>

<WhatGoesOnTheBoard>

Anything from a raw idea to work in flight. The existing draft-vs-promoted
item model carries the stage — **no schema change needed**:

- **Idea / not yet committed to** → a **DRAFT** item on the board (no repo
  issue, no local file). Safe to capture, triage, and discard.
- **Decided to do** (the gate) → **promote** to a real Issue, and start its
  development lifecycle (branch → PR).

Decide the shape from the requirement by decomposing it along the codebase's
structural seams (layers / modules / concerns):

- The decomposition yields **a single sub-goal** that fits one reviewable PR
  → a **single Issue**.
- It yields **two or more independent sub-goals** → a **Parent Issue (epic)**
  with one sub-issue per sub-goal.
- "One or several?" is unclear → the decomposition is not finished; decompose
  again. A single increment that still feels huge is a signal to keep
  decomposing, not to ship a giant one-commit PR.

Hierarchy:

```
Parent Issue (epic) … the high-level requirement
 └ Phase … a wave / dependency order, written in the epic body as `### Phase N`
    └ Sub-issue … one reviewable PR-sized unit, referenced as `#n`
       └ Commit … the steps stacked inside that PR
```

- A sub-issue maps to one PR. Whether several small structural pieces inside a
  sub-goal become separate sub-issues or commits inside one PR depends on
  whether each is independently reviewable. A sub-issue's body is its per-Kind
  sections (Requirements / Acceptance) plus, when the work isn't obvious, a
  `## Approach` outline (main steps, files touched, approach — no code) so an
  agent or fresh session can pick it up without re-exploring.
- Sub-issues live in the repo (not on the board); the epic carries progress via
  its sub-issue bar.
- Neutral example: "add an external login" decomposes along the seams into
  backend auth wiring, the login UI, and route protection — three independent
  sub-goals, so an **Epic**. The backend piece stays one sub-issue (one PR)
  whose internal steps are commits; it does not become three sub-issues unless
  each is independently reviewable. Its `## Approach` names the provider
  strategy, the module registration, and the guard wiring; the epic's
  `## Acceptance` covers the end-to-end login→protection flow no single
  sub-issue verifies alone.

</WhatGoesOnTheBoard>

<BranchTopology>

- **One issue = one branch.** On promote/issue-creation, open a linked
  development branch with `github_project_issue_develop`. It appears in the
  issue's Development panel; a PR opened from it links there automatically.
- **Stacked.** For an epic, the epic has its own branch off the default branch;
  each sub-issue's branch is created off the **epic branch** (`base`), so its
  PR targets the epic branch (a stacked PR). When all sub-issues land, the epic
  branch is PR'd into the default branch.
- **Single issue** → its branch is PR'd straight into the default branch.
- Delegate: branch creation to `github_project_issue_develop` (or `git-commit`
  for plain branches), PR creation to `git-pullrequest` (it detects the stacked
  base). Use `github_project_issue_link` to attach sub-issues to the epic.

</BranchTopology>

<Steps>

1. **Triage & capture.** New idea or requirement → add a DRAFT item
   (`github_project_item_add`) with Kind / Area / `_Repository` (+
   `_Milestone` theme). It is safe to capture before committing to do it.
2. **Decompose (at the spine's "align on a plan" checkpoint).** Break the
   requirement along the codebase's seams into reviewable sub-goals. The count
   decides the shape: one → single Issue; several → Parent Issue + sub-issues
   (per `<WhatGoesOnTheBoard>`). If unsure, keep decomposing.
3. **Gate — promote + wire.** When decided:
   - `github_project_item_promote` the item to a real Issue.
   - `github_project_issue_develop` to open its linked branch (epic off the
     default branch; sub-issue off the epic branch for stacking; `checkout`).
   - For an epic, `github_project_issue_link` to attach each sub-issue (it sets
     the sub-issue's Issue Type to `Task`). Write the epic body's `## Plan`
     with `### Phase N` and `#n` sub-issue references.
   - Fill each sub-issue's body with its per-Kind sections (Requirements /
     Acceptance) and, when the work isn't obvious, a `## Approach` outline so it
     can be picked up without re-exploring.
4. **Execute via stacked PRs.** Implement each sub-issue on its branch; open a
   PR to its base via `git-pullrequest`. Land each PR (it closes its
   sub-issue); keep the epic's Plan in sync as sub-issues change. A single
   Issue just PRs to the default branch.
5. **Close the loop.** When all sub-issues land, run the epic's `## Acceptance`
   integration checks (end-to-end, no regressions) before merging; then PR the
   epic branch into the default branch — merging closes the epic. Set the board
   item Status to Done and summarize the outcome. No orphan local plan/TODO
   files.
6. **Re-enter across sessions.** At the start of a session,
   `github_project_item_list` (`-status:Done -status:Cancelled`) → read the
   epic's `## Plan` → `checkout` the relevant branch → resume.

</Steps>

<AntiPatterns>

- Do not put a giant single-commit PR behind a lone Issue when the work has
  several sub-goals — decompose into an epic first.
- Do not confuse a DRAFT (idea, not committed to) with a promoted Issue
  (decided, in flight).
- Do not run an issue without a linked development branch; the Development
  panel is the cross-session source of truth for "where is this work".
- Do not break the stack: a sub-issue's PR targets the **epic branch**, not the
  default branch directly.
- Do not dump every sub-task onto the board — the board tracks epics and
  single issues; sub-issues stay in the repo.
- Do not leave the plan in a local TODO/plan/notes file — it lives on the board
  and in the epic body.

</AntiPatterns>

<Gates>

- [ ] Ideas are DRAFT items; decided work is promoted — no schema confusion.
- [ ] Shape chosen by decomposition: one sub-goal → single Issue; several →
  epic with sub-issues.
- [ ] Every issue has a linked development branch; sub-issues stack under the
  epic branch.
- [ ] Sub-issues linked to the epic (Type `Task`); epic `## Plan` kept in sync.
- [ ] Re-enterable: `item_list` → epic Plan → branch checkout resumes the work.
- [ ] No orphan local plan/TODO files; the board and epic body are the record.

</Gates>
