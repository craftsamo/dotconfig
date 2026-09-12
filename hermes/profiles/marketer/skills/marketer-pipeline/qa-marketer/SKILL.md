---
name: qa-marketer
description: >-
  QA marketing: check strategy, content and saved drafts. Read-only acceptance
  against the released goal and evidence; not an effectiveness analysis,
  repair or new save.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [quality-assurance, marketing]
    category: marketer-pipeline
---

<ReadBeforeWork>

Re-evaluate this entry on each user turn or completion and before a mode,
target, platform or scope-changing action. Reuse full-body instructions only
while present in the current context, never a past load or summary. Before
work, including direct entry, load the kernel if its full body is missing:

```text
skill_view(name="marketer-pipeline")
```

This entry is the complete mode procedure. Read only its applicable detail
references below. A reference owned by another entry requires that entry and
the kernel before application. Loading instructions does not restart the job,
reset approvals or expand a grant.

If skill_view returns unchanged while the earlier body is unavailable, use
read_file on `${HERMES_SKILL_DIR}/../SKILL.md` for the kernel and
`${HERMES_SKILL_DIR}/SKILL.md` for this entry; resolve each detail from its
owning skill directory. Follow next_offset until the required body is
complete. Do not evade dedup with alternate paths or artificial ranges. If the
body remains missing, stop the affected action and report it.

Read shared [state](../references/state.md) for records, approvals or
resumes. For a named service, read only its applicable shared procedure:
[X](../references/platforms/x.md), [Substack](../references/platforms/substack.md),
[note](../references/platforms/note.md) or [Zenn](../references/platforms/zenn.md).
Instruction reads do not authorize browser work. Any actual browser action,
including verification or measurement, requires the kernel's
[browser lease](../scripts/browser-lease.py) contract and the relevant shared
procedure.

</ReadBeforeWork>

# Quality assurance

Select the actual object and released scope:

- [strategy](references/strategy.md): a proposed direction, offer or experiment;
- [content](references/content.md): intended text/media before remote editor entry;
- [saved draft](references/saved-draft.md): the service-side saved object after Build.

Read the actual artifact, sources and relevant decisions, not a peer's reply
summary. Report checked, unmet and unverified requirements distinctly. Missing
required evidence cannot pass; unrelated future work does not expand a bounded
edit's acceptance scope. A no-op edit or findings-only report can be correct.

Do not repair during inspection. Return a concrete defect to its owner, then
read the changed result; previous acceptance does not cover new bytes or assets.
Keep user taste/strategy decisions separate from verifiable requirements.

Writer requester scoring belongs to the shared contract referenced by
[content](references/content.md). Do not invent additional scores for marketing outcomes,
legal certainty or platform support. Strategy self-check is not independent
market validation, and a saved draft is not a published post. Marketing effect
belongs to [Analyze](../analyze-marketer/SKILL.md), never a reason to waive content checks.
