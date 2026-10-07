---
name: qa-assistant-engineering
description: "QA engineering: accept Client outcomes against PR evidence. Inspect reports and actual work without duplicating technical review; acceptance grants no merge, deployment or automatic Issue updates."
version: 1.0.0
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

# Engineering - Client acceptance

Judge the delivered outcome against the user's request and approved scope.
Engineer already owns technical QA, rendered UI inspection and independent UX
evaluation. Do not duplicate that pipeline or recreate its technical plan here.
The artifact is the report plus actual PR/worktree evidence, not a compulsory
draft file under .agent/. The common floor in ../index.md still applies.

1. Match requested outcomes to concrete evidence: changed behavior, tests and
   actual results, rendered evidence where applicable, and stated limitations.
2. Confirm the PR exists with the intended repository/base/head and scope.
   A local-only exception or a blocked PR is reported as such, not fabricated.
   Use [inspection.md](references/inspection.md) for Client-level acceptance expectations.
3. Spot-check evidence when needed, without making every Client run repeat
   Engineer's test suite. Unclear or high-risk evidence requests an additional
   Engineer investigation/review, not a competing Assistant OpenCode session.
4. Accept, return evidence-anchored defects, or reopen the agreed scope with the
   user. Do not turn a changed preference into an undisclosed implementation bug.

No edits, commits, reverts, Issue mutations or browser production side effects
during acceptance. Repairs return to Engineer with expected behavior and evidence.
An unresolved required check is not a pass. A plan/diagnosis/review is accepted
for the requested answer, without demanding an implementation or PR.

[acceptance.md](references/acceptance.md) covers PR completion and separately requested
merge/Issue close-out. Passing this QA does not authorize merge or deployment,
and it does not automatically update Issues or a project board.
