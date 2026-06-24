---
name: approach-roadmap
description: >-
  Use when durable, multi-step, or cross-session work from an approach should
  live on the GitHub Projects "Roadmap" board — turn a co-designed plan into a
  tracked epic + phased sub-issues (or a single item) and drive it to done
  (ロードマップ, 計画をボードに, エピック, 起票して進める, track work, roadmap,
  epic). Apply on top of the `approach` spine; delegate board mechanics to the
  `manage-github-projects` skill. Use ONLY to orchestrate planning ↔ board, not
  for board mechanics themselves.
---

<Goal>

Persist a co-designed plan on the "Roadmap" board and drive it to done across
sessions, so nothing lives in throwaway local TODO/plan files. Apply on top of
the `approach` spine (investigate → confirm the goal → co-design → small
reversible steps); delegate all board operations — schema, item/epic creation,
body formats, status, promote — to the `manage-github-projects` skill.

</Goal>

<WhenToUse>

- Durable / multi-session / multi-step work → record and track it on the board.
- Ephemeral within-session steps → keep using TodoWrite, not the board.
- Cross-cutting companion: layer it on any scenario playbook (new-feature,
  rebuild-migration, …) once the work is worth persisting.

</WhenToUse>

<Steps>

1. Pick the unit (at the spine's "align on a plan" checkpoint): a single board
   item for small work, or an epic + `### Phase N` sub-issues for large
   multi-step work.
2. Materialize on the board via `manage-github-projects`: set Kind / Area /
   _Repository (+ _Milestone theme). For an epic, write the Overview + phased
   Plan and create the sub-issues in the repo (single-purpose, repo template).
3. Drive in small steps (spine step 5): move Status Todo → In Progress → Done,
   append decisions / notes to the item, close each sub-issue as it lands, and
   keep the epic's Plan in sync when steps are added or dropped.
4. Close the loop: when all sub-issues are done, close the epic and summarize the
   outcome on the item.

</Steps>

<Gates>

- [ ] Durable plan lives on the board; no orphan local TODO/plan/notes files.
- [ ] Large work is an epic with phased sub-issues; small work is a single item.
- [ ] Status and notes kept current as steps land.
- [ ] Epic closed and outcome summarized when the work is done.

</Gates>
