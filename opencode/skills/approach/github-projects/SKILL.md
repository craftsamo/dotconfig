---
name: approach-github-projects
description: >-
  Use when durable, multi-step, or cross-session work from an approach should
  live on GitHub Projects — decompose a high-level requirement into an epic
  whose direct sub-issues are PURPOSE issues (the "do this now" execution
  unit, sized 1–3 PRs, spec Draft→Fixed at kickoff), then execute each purpose
  as a native GitHub stack of PRs rooted at the default branch, grown one
  layer at a time (ロードマップ, 計画をボードに, エピック, 目的 Issue,
  Parent issue, Sub-issue, 起票して進める, track work, roadmap, epic,
  stacked PR, gh stack, development branch). Layers on any approach-* scenario
  skill; delegates board mechanics and body formats to `manage-github-projects`
  and PR creation to `git-pullrequest`. Use ONLY to orchestrate planning ↔
  GitHub Projects, not for board mechanics themselves.
author: CraftSamo
license: MIT
---

<Goal>

Persist a co-designed plan on GitHub Projects and drive it to done across
sessions, so nothing lives in throwaway local TODO/plan files. Once a plan is
co-designed (investigate → confirm the goal → co-design → small reversible
steps), decompose the requirement into an epic whose execution units are
**purpose issues**, defer PR-level decomposition to each purpose's kickoff,
and execute each purpose as a native GitHub stack of PRs rooted at the default
branch. Delegate board operations and issue body formats to
`manage-github-projects` and PR creation to `git-pullrequest`.

</Goal>

<WhenToUse>

- Durable / multi-session / multi-step work → record and track it on the board.
- Ephemeral within-session steps → keep using TodoWrite, not the board.
- Cross-cutting companion: layer it on any scenario playbook (new-feature,
  rebuild-migration, …) once the work is worth persisting.

</WhenToUse>

<Hierarchy>

Issues stop at the purpose; below it the unit of work is a PR, not an issue:

```
Board item … the EPIC only (never purposes — keep the org Roadmap noise-free)
Epic (parent issue) … the high-level requirement; tracking only
 └ Purpose issue … ONE purpose, the execution unit ("do this now"),
    │              sized 1–3 reviewable PRs; carries its own spec
    │              (Requirements Draft→Fixed) and implementation outline
    └ Stack layer … one reviewable PR in the purpose's native GitHub stack;
       │            NOT an issue — its slice spec lives in the PR body
       └ Commit … the steps inside that PR
```

There is deliberately **no work sub-issue tier**. A work issue and its PR
carried the same Scope / Acceptance twice, and the PR is the better home: it
holds the diff, the checks and the review threads alongside the spec. The
purpose's `## Implementation outline` is a plain checklist of planned layers,
so re-slicing the plan costs a text edit rather than issue surgery.

Shape selection (decompose along the codebase's structural seams):

- One standalone sub-goal that fits one PR (no epic context) → a **single
  issue**.
- One purpose-sized sub-goal (1–3 PRs) → a **single purpose issue** (no epic).
- Several purpose-sized sub-goals → an **epic** with purpose issues.
- Inside an epic, a purpose that turns out to be one PR stays a purpose issue
  and simply needs no stack (see `<BranchTopology>`).
- An epic that would decompose directly into ~5+ PR-sized units, or spans
  several domains, is the signal that the purpose tier is missing — insert it.
  A "purpose" is the smallest unit that delivers a meaningful outcome on its
  own; if picking it up for the week feels heavy, it is still an epic-sized
  lump: keep decomposing.
- A short-lived feature that must land atomically is modeled as a **purpose
  issue**, not an epic — a purpose's stack merges atomically, an epic has no
  branch or stack of its own (see `<BranchTopology>`).

The epic's `## Plan` orders purposes into dependency waves (a Wave table or
`### Wave N` headings); each purpose issue additionally names its own
`## Dependencies`. Body formats for the epic, the purpose and the stack-layer
PR are defined in `manage-github-projects` `<BodyGuidance>`.

</Hierarchy>

<ResearchModel>

Each tier investigates different questions, at different times, recorded in
different places. Research never gets its own standalone issue.

| Tier | Research | Question | When | Recorded where |
| --- | --- | --- | --- | --- |
| Epic | Domain: market, competitors, primary sources, business constraints | What should we build? | Around epic creation | Epic **comments** hold the full reports (the originals); the epic body's `## Details` holds only the distilled constraints / principles / seams |
| Purpose | System: existing code assets, port sources, library / provider comparison, integration seams | How do we realize this purpose here? | At the purpose's **kickoff** (the Draft→Fixed gate) | The purpose issue's `## Research` — transcribe the epic-research excerpts it depends on (self-contained even if source issues close) plus its own findings; conclusions resolve `## Open decisions` into `## Requirements` |
| Stack layer | Implementation detail: file locations, conventions, API shapes, how to run tests | Where and how do we change it? | Inline during implementation | Not persisted as issue content — the PR body's Scope and the diff itself are the record |

Flow is bidirectional:

- **Down**: epic research → each purpose transcribes the excerpts it relies on.
- **Up**: a discovery during work that exceeds its scope is NOT absorbed on the
  spot — escalate it to the purpose's `## Open decisions` (system-level) or an
  epic comment (domain-level), then continue.

</ResearchModel>

<SpecLifecycle>

Purpose issues carry a two-stage spec, tracked by body header lines
(`**Requirement status**: Draft | Fixed`):

1. **Draft (at planning).** Created with provisional `## Requirements`, an
   `## Implementation outline` (expected PR slices, prose only), and
   `## Open decisions` (what must be settled at kickoff). This is deliberate:
   later purposes' PR boundaries depend on earlier implementations, so
   decomposing everything up front causes rework.
2. **Fixed (at kickoff).** When a purpose is picked up: run its system
   research (`<ResearchModel>`), settle `## Open decisions` with the user,
   update the body (Draft → Fixed, decisions folded into Requirements), and
   turn `## Implementation outline` from prose into a checklist of the planned
   stack layers. The checklist stays editable: re-slice it freely while the
   layers above it are still unwritten.

Only purposes derived from an already-confirmed spec start as Fixed.

</SpecLifecycle>

<BranchTopology>

A purpose executes as one **native GitHub stack** (`gh stack`) whose trunk is
always the default branch.

- **Epics have no branch.** They are tracking-only; a months-long epic branch
  would starve the default branch and rot. The epic's progress is its
  sub-issue bar.
- **Purposes have no merge-vehicle branch either.** A purpose is a spec and a
  tracking unit, not a place to accumulate merged work. Its layers land on the
  default branch, so the default branch never falls a purpose behind.
- **One purpose = one stack; one layer = one PR.** The shape is
  `main ← layer1 ← layer2 ← …`. Name every layer branch after the purpose
  (`<purpose-number>-<slug>/l1`, `/l2`, …) so any layer traces back to it
  without a lookup.
- **A multi-layer purpose gets NO linked development branch.**
  `github_project_issue_develop` registers the branch in the issue's
  `closingIssuesReferences` even with no closing keyword anywhere, so the
  first layer to merge closes the purpose while the layers above it are still
  open. Use plain branches instead (`git-commit` creates them). This is the
  one place where the Development panel costs more than it gives.
- **Grow the stack, do not pre-build it.** Add a layer only when you are about
  to implement it (`gh stack top` then `gh stack add`). The CLI can only append
  to the top: inserting or reordering needs `gh stack modify`, which is TUI-only
  and not drivable from a session. Keeping unwritten layers as outline text
  instead of PRs is what keeps the plan re-sliceable.
- **The trunk is the default branch, always.** A non-default trunk is possible
  (`gh stack init --base`) but poisoned: closing keywords do not fire for the
  layers of such a stack, and it re-introduces two kinds of PR with different
  rules. One trunk, one kind of PR.
- **Closing.** Intermediate layers carry `Refs #<purpose>`; the layer that
  completes the purpose carries `Closes #<purpose>` **instead** (the closing
  keyword is itself the reference) — normally the top one, and move it if you
  append another layer above. Closing keywords fire from any layer of a
  default-branch-rooted stack, so this is the whole mechanism: intermediate
  layers can land without ending the purpose. Fill the purpose's
  `## Evidence` before that last layer merges.
- **Degenerate case**: a one-PR purpose needs no stack — here
  `github_project_issue_develop` is right, because closing the purpose when
  its single PR lands is exactly the desired behavior.
- Delegate: branch creation to `git-commit` (or `github_project_issue_develop`
  for a one-PR purpose), PR and stack bookkeeping to `git-pullrequest`.

</BranchTopology>

<Steps>

1. **Triage & capture.** New idea or requirement → add a DRAFT board item
   (`github_project_item_add`) with Kind / Area / `_Repository` (+
   `_Milestone` theme). Safe to capture before committing to do it.
2. **Decompose (when aligning on the plan).** Break the requirement along the
   codebase's seams into purpose-sized sub-goals (`<Hierarchy>`). Record
   domain research as epic comments; write each purpose issue per
   `manage-github-projects` `<BodyGuidance>` (Draft spec + outline + open
   decisions). Order purposes into waves in the epic's `## Plan`. Create
   purposes in dependency order so `## Dependencies` uses real `#n` numbers.
3. **Gate — promote + wire.** When decided: `github_project_item_promote` the
   board item to the real epic issue (the board tracks ONLY this epic);
   `github_project_issue_link` each purpose under the epic (Type `Task`).
   Do NOT create branches yet.
4. **Kickoff a purpose (repeat per purpose).** Pick the next purpose by the
   Wave table: run its system research → settle Open decisions → update the
   body to Fixed with `## Implementation outline` as a layer checklist →
   `gh stack init <purpose-number>-<slug>/l1` off the default branch. A one-PR
   purpose instead takes a linked branch via `github_project_issue_develop`.
5. **Execute layer by layer.** Implement the current layer, PR it via
   `git-pullrequest`, then `gh stack top` + `gh stack add` for the next one.
   Tick the outline checklist as layers land. After changing a lower layer,
   `gh stack rebase` then `gh stack push` — the stack cannot merge unless each
   layer is a linear descendant of the one below. Land with `gh stack merge`
   (atomic: if any layer is not mergeable, none merge); merging the top layer
   closes the purpose. Keep the epic's Plan in sync.
6. **Close the loop.** When all purposes land, run the epic's `## Acceptance`
   integration checks, close the epic, set the board item Status to Done, and
   summarize. No orphan local plan/TODO files.
7. **Re-enter across sessions.** `github_project_item_list`
   (`-status:Done -status:Cancelled`) → read the epic's `## Plan` → open
   purposes' status headers → resume the in-flight purpose: its timeline
   cross-references the layer PRs (each carries `Refs #<purpose>`), and
   `gh stack checkout <any layer branch or PR number>` restores the whole
   stack, with `gh stack view` showing what has landed.

</Steps>

<SupersedeProtocol>

When restructuring changes the issue topology (splitting, merging, or
re-tiering existing issues), never delete and never leave dangling parents:

1. Create the successor issues first (transcribe the content they inherit —
   requirements, research excerpts, decisions — so each successor is
   self-contained).
2. Comment on each superseded issue: what replaced it and where the content
   went (successor `#n` list).
3. Unlink it from its parent (`github_project_issue_link` mode `remove`), then
   close it — `completed` if its job was finished (e.g. a spec that was
   confirmed and transcribed), `not planned` if it was replaced mid-flight.
4. Re-parent surviving sub-issues onto the successors (mode `set-parent`), and
   split any sub-issue that now spans two successors.

Closed superseded issues remain readable as originals; successors link back
(via `## Evidence` on a purpose, or `**Refs**:` on other tiers).

</SupersedeProtocol>

<AntiPatterns>

- Do not decompose every purpose into PR slices up front — later PR boundaries
  depend on earlier implementations; slice at kickoff, and only into outline
  text.
- Do not open the whole stack as draft PRs before implementing it — empty
  layers cannot become PRs at all, placeholder commits and their CI runs are
  pure waste, and mid-stack insertion is TUI-only afterwards.
- Do not file work sub-issues for stack layers — the layer's PR body is its
  spec; a parallel issue is duplicate bookkeeping that goes stale.
- Do not open a linked development branch for a multi-layer purpose — the
  link closes the purpose as soon as the first layer merges.
- Do not create an epic branch or a purpose merge-vehicle branch — epics are
  tracking-only and purposes land layer by layer on the default branch.
- Do not put purposes on the board — the board carries the epic (and
  standalone tasks) only; anything more is Roadmap noise.
- Do not create research-only issues — domain research lives in epic comments,
  system research inside the purpose issue that consumes it.
- Do not leave a purpose in Draft while implementing it — Fixed (settled
  decisions, updated body) gates the slicing.
- Do not write `Parent: #n` in issue bodies — the native sub-issue panel is
  the single source of parentage; body copies go stale on re-parenting.
- Do not absorb out-of-scope discoveries mid-implementation — escalate up
  (`<ResearchModel>`) and keep the layer's PR on scope.
- Do not confuse a DRAFT board item (idea) with a promoted epic (decided).
- Do not leave the plan in a local TODO/plan/notes file — it lives on the
  board and in the epic and purpose bodies.

</AntiPatterns>

<Gates>

- [ ] Ideas are DRAFT board items; decided work is a promoted epic — the board
  carries epics and standalone items only, never an epic's descendants.
- [ ] Shape chosen by decomposition: 1 PR → single issue; 1–3 PRs → purpose;
  several purposes → epic (purpose tier inserted, no direct epic→PR lumps).
- [ ] Every purpose body carries its spec status; Draft purposes have Open
  decisions, Fixed purposes have a layer checklist in the outline.
- [ ] Research is tiered: epic comments (domain) / purpose `## Research`
  (system, transcribed + self-contained) / none persisted at layer tier.
- [ ] Branches: the stack trunk is the default branch, layers are named after
  the purpose and appended only as they are implemented; no epic branch, no
  purpose merge vehicle, and no linked development branch on a multi-layer
  purpose (it would close the purpose at the first merge).
- [ ] Exactly one layer carries `Closes #<purpose>` (the last one); every
  other layer carries `Refs #<purpose>` instead.
- [ ] Superseded issues are closed with successor links, never deleted; no
  stale `Parent:` lines in bodies.
- [ ] Re-enterable: `item_list` → epic Plan → purpose status → branch checkout
  resumes the work.

</Gates>
