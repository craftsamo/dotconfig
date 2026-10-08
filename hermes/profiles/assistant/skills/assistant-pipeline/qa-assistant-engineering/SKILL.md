---
name: qa-assistant-engineering
description: "QA engineering: accept outcomes against PR and worktree evidence, with an independent OpenCode review for risky changes and rendered evidence for UI. Acceptance grants no merge, deployment or automatic Issue updates."
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["quality-assurance", "engineering"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/quality-assurance/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/quality-assurance/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Engineering - acceptance

Before the first `opencode_*` call, load the tool mechanics with
`skill_view(name="opencode:opencode")` unless its full body is already in the
current context.

Judge the delivered outcome against the user's request and the approved scope.
OpenCode already runs the project's checks and its own review passes; do not duplicate that pipeline or rerun every suite. Your part
is evidence, independence and the user's intent. The artifact is the report
plus the actual PR and worktree, not a compulsory draft file. The common floor
in ../index.md still applies.

1. **Scope.** Read the actual diff (`opencode_session diff`, Git) and
   pre-existing changes: no stray files, unrelated edits, unapproved
   dependencies or scope creep.
2. **Evidence.** Match each requested outcome to concrete evidence: changed
   behavior, tests and their actual output (assertions not weakened to fit a
   bug), and stated limitations. A bug fix replays the original symptom;
   performance compares the same measured workload; a refactor preserves
   behavior; a migration reconciles data and its recovery. A missing facility
   or credential leaves that check unverified, never passed.
3. **Independent review** for a risky or non-trivial change (auth, data shape,
   concurrency, public API, migrations, money): a NEW `opencode_run_review`
   session on the worktree with the requirement and the current diff, not the
   implementation conversation's claims ("deep review <area>" for the risky
   part). It runs on a model other than yours. A small mechanical change needs
   only your diff read.
4. **Rendered UI.** For a change to what a page looks like, read the build's
   rendered evidence (screenshots tied to the changed build, the target
   viewports and states) and show the user the screenshots when the look itself
   is the decision. Never open a development target in your own logged-in
   browser profile.
5. **PR.** Confirm the PR exists with the intended repository, base, head,
   commits and description, and read its CI state: pending or unavailable is
   not green, a failed required check prevents unqualified acceptance. A
   local-only exception or a blocked PR is reported as such.
6. **Verdict.** Accept, return evidence-anchored defects to the same build
   session, or reopen the agreed scope with the user. Do not turn a changed
   preference into an undisclosed implementation bug.

Use [inspection.md](references/inspection.md) for archetype evidence. No edits,
commits, reverts, Issue mutations or browser production side effects during
acceptance; repairs go back to the build session with expected behavior and
evidence. An unresolved required check is not a pass. A plan, diagnosis or
review is accepted for the requested answer, without demanding a PR.

[acceptance.md](references/acceptance.md) covers PR completion and separately
requested merge/Issue close-out. Passing this QA does not authorize merge or
deployment, and it does not automatically update Issues or a project board.
