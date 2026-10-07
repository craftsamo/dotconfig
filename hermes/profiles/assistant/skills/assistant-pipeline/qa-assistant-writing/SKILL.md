---
name: qa-assistant-writing
description: "QA writing: apply the shared requester acceptance contract. Load Writer acceptance and the selected family branch; missing instructions block acceptance, never a generic review or self-report pass."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["quality-assurance", "writing"]
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

Use [references/prose.md](references/prose.md) for reader-facing prose or
[references/script.md](references/script.md) for producer-facing scripts;
each adapter loads the applicable public Writer acceptance branch.

</ReadBeforeWork>

# Writing QA — the per-unit gate

The writing-acceptance contract (served post/article/document/message/copy/
script gates, the outline/full gate, evidence-anchored scoring, correction
ceiling and Contract files) is no longer duplicated here. It is owned by
Writer's own public pipeline, exactly as any other caller of `specialist_call`
reads it, so the rubric has one definition instead of a private fork.

Load it with:

```text
skill_view(name="writer-pipeline", file_path="references/acceptance/index.md")
```

and the matching family branch through the same skill (`references/acceptance/prose.md`
or `references/acceptance/script.md`). Read only the branch the released
request selects; do not copy either file's text into this repo.

## If the load fails

The skill is missing, unreadable, or the named file does not resolve: this
acceptance is BLOCKED. Do not fall back to a generic review, invent criteria,
or accept on Writer's self-report alone — the common floor's "cannot verify ≠
pass" rule extends to the contract itself. Record the exact skill/file name
and the failure in the job's QA record, and return the unit unresolved rather
than deliver a guessed pass.

## What stays here

Nothing acceptance-specific. Planning routes to `../plan-assistant-writing/SKILL.md` from
`../references/plan/index.md`; execution mechanics after acceptance live in
`../execute-assistant-writing/SKILL.md`; this file is only the pointer the writing
capability row resolves to.
