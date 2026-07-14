---
name: approach-github-projects
description: >-
  Use when durable, multi-step, or cross-session work from an approach should
  live on GitHub Projects — decompose a high-level requirement into an epic
  whose direct sub-issues are PURPOSE issues (the "do this now" execution
  unit, sized 1–3 PRs, spec Draft→Fixed at kickoff), each decomposed into
  PR-sized work sub-issues at kickoff, and drive it to done through linked
  development branches (purpose → main; work PRs stack under the purpose
  branch) (ロードマップ, 計画をボードに, エピック, 目的 Issue, Parent issue,
  Sub-issue, 起票して進める, track work, roadmap, epic, stacked PR,
  development branch). Layers on any approach-* scenario skill; delegates
  board mechanics and body formats to `manage-github-projects` and PR
  creation to `git-pullrequest`. Use ONLY to orchestrate planning ↔ GitHub
  Projects, not for board mechanics themselves.
---

<Goal>

Persist a co-designed plan on GitHub Projects and drive it to done across
sessions, so nothing lives in throwaway local TODO/plan files. Once a plan is
co-designed (investigate → confirm the goal → co-design → small reversible
steps), decompose the requirement into an epic whose execution units are
**purpose issues**, defer PR-level decomposition to each purpose's kickoff,
and wire each purpose into a linked development branch and stacked work PRs.
Delegate board operations and issue body formats to `manage-github-projects`
and PR creation to `git-pullrequest`.

</Goal>

<WhenToUse>

- Durable / multi-session / multi-step work → record and track it on the board.
- Ephemeral within-session steps → keep using TodoWrite, not the board.
- Cross-cutting companion: layer it on any scenario playbook (new-feature,
  rebuild-migration, …) once the work is worth persisting.

</WhenToUse>

<Hierarchy>

Three tiers, sized so that "what we do now" is always a small, visible unit:

```
Board item … the EPIC only (never purposes or work issues — keep the org
             Roadmap noise-free)
Epic (parent issue) … the high-level requirement; tracking only
 └ Purpose issue … ONE purpose, the execution unit ("do this now"),
    │              sized 1–3 reviewable PRs; carries its own spec
    │              (Requirements Draft→Fixed) and implementation outline
    └ Work sub-issue … one reviewable PR; created at the purpose's kickoff
       └ Commit … the steps inside that PR
```

Shape selection (decompose along the codebase's structural seams):

- One standalone sub-goal that fits one PR (no epic context) → a **single
  issue**.
- One purpose-sized sub-goal (1–3 PRs) → a **single purpose issue** (no epic).
- Several purpose-sized sub-goals → an **epic** with purpose issues.
- Inside an epic, a purpose that turns out to be one PR stays a purpose issue
  and simply skips the work tier (see `<BranchTopology>`).
- An epic that would decompose directly into ~5+ PR-sized units, or spans
  several domains, is the signal that the purpose tier is missing — insert it.
  A "purpose" is the smallest unit that delivers a meaningful outcome on its
  own; if picking it up for the week feels heavy, it is still an epic-sized
  lump: keep decomposing.
- A short-lived feature that must land atomically is modeled as a **purpose
  issue**, not an epic — epics never get their own branch (see
  `<BranchTopology>`).

The epic's `## Plan` orders purposes into dependency waves (a Wave table or
`### Wave N` headings); each purpose issue additionally names its own
`## Dependencies`. Body formats for all three tiers are defined in
`manage-github-projects` `<BodyGuidance>`.

</Hierarchy>

<ResearchModel>

Each tier investigates different questions, at different times, recorded in
different places. Research never gets its own standalone issue.

| Tier | Research | Question | When | Recorded where |
| --- | --- | --- | --- | --- |
| Epic | Domain: market, competitors, primary sources, business constraints | What should we build? | Around epic creation | Epic **comments** hold the full reports (the originals); the epic body's `## Details` holds only the distilled constraints / principles / seams |
| Purpose | System: existing code assets, port sources, library / provider comparison, integration seams | How do we realize this purpose here? | At the purpose's **kickoff** (the Draft→Fixed gate) | The purpose issue's `## Research` — transcribe the epic-research excerpts it depends on (self-contained even if source issues close) plus its own findings; conclusions resolve `## Open decisions` into `## Requirements` |
| Work | Implementation detail: file locations, conventions, API shapes, how to run tests | Where and how do we change it? | Inline during implementation | Not persisted as issue content — the Scope/Approach and the PR itself are the record |

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
   update the body (Draft → Fixed, decisions folded into Requirements), then
   create the PR-sized work sub-issues and link them under the purpose.

Only purposes derived from an already-confirmed spec start as Fixed.

</SpecLifecycle>

<BranchTopology>

- **Epics have no branch.** They are tracking-only; a months-long epic branch
  would starve the default branch and rot. The epic's progress is its
  sub-issue bar.
- **One purpose = one branch = one PR to the default branch.** On kickoff,
  open a linked development branch with `github_project_issue_develop` off the
  default branch. The purpose lands as a unit; its branch lives days-to-a-week,
  so the stack stays bounded.
- **Work sub-issues stack under the purpose branch.** Each work branch is
  created off the purpose branch (`base`), its PR targets the purpose branch,
  and review happens per work PR. The final purpose → default-branch PR is a
  merge vehicle — already-reviewed content, no re-review.
- **Degenerate case**: a purpose that is one PR skips the work tier; its
  branch PRs straight to the default branch.
- Delegate: branch creation to `github_project_issue_develop` (or `git-commit`
  for plain branches), PR creation to `git-pullrequest` (it detects the
  stacked base). Use `github_project_issue_link` to attach sub-issues.

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
   body to Fixed → create + link its work sub-issues →
   `github_project_issue_develop` its branch off the default branch, and each
   work branch off the purpose branch.
5. **Execute via stacked PRs.** Implement each work sub-issue on its branch;
   PR to the purpose branch via `git-pullrequest`; landing it closes the work
   sub-issue. When all land, PR the purpose branch into the default branch
   (merge vehicle) — merging closes the purpose. Keep the epic's Plan in sync.
6. **Close the loop.** When all purposes land, run the epic's `## Acceptance`
   integration checks, close the epic, set the board item Status to Done, and
   summarize. No orphan local plan/TODO files.
7. **Re-enter across sessions.** `github_project_item_list`
   (`-status:Done -status:Cancelled`) → read the epic's `## Plan` → open
   purposes' status headers → resume the in-flight purpose (its Development
   panel names the branch).

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

- Do not decompose every purpose into PR-sized work issues up front — later
  PR boundaries depend on earlier implementations; decompose at kickoff.
- Do not create an epic branch or stack work under one — epics are
  tracking-only; a purpose is the landing unit.
- Do not put purposes or work sub-issues on the board — the board carries the
  epic (and standalone tasks) only; anything more is Roadmap noise.
- Do not create research-only issues — domain research lives in epic comments,
  system research inside the purpose issue that consumes it.
- Do not leave a purpose in Draft while implementing it — Fixed (settled
  decisions, updated body) gates the work decomposition.
- Do not write `Parent: #n` in issue bodies — the native sub-issue panel is
  the single source of parentage; body copies go stale on re-parenting.
- Do not absorb out-of-scope discoveries mid-implementation — escalate up
  (`<ResearchModel>`) and keep the work PR on scope.
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
  decisions, Fixed purposes have linked work sub-issues.
- [ ] Research is tiered: epic comments (domain) / purpose `## Research`
  (system, transcribed + self-contained) / none persisted at work tier.
- [ ] Branches: purpose → default branch; work PRs stack under the purpose
  branch; epics have no branch.
- [ ] Superseded issues are closed with successor links, never deleted; no
  stale `Parent:` lines in bodies.
- [ ] Re-enterable: `item_list` → epic Plan → purpose status → branch checkout
  resumes the work.

</Gates>
