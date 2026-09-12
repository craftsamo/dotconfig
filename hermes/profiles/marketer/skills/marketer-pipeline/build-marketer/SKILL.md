---
name: build-marketer
description: >-
  Build marketing: commission parts and prepare service drafts. Supervise
  approved work and observations; exact remote-save consent is separate.
  Never publish, schedule or send.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [build, marketing]
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

# Build

Read the released request and [state](../references/state.md). Determine which work is
authorized now: commission a part, create/update a service draft, or observe
results. Preserve the distinction between proposed, accepted and user-approved.
An inquiry over inbound A2A does not authorize browser work or resident children.

1. Resolve inputs and the private job location. Unknown audience/offer is a
   [Plan](../plan-marketer/SKILL.md) task only when it blocks the released purpose, not
   something to fabricate or a reason to re-plan a bounded punctuation edit.
2. Obtain parts through [parts](references/parts.md), then run
   [content QA](../qa-marketer/references/content.md). A producer receipt is evidence
   to inspect, not independent acceptance.
3. For a service-side draft use [draft](references/draft.md) and the selected platform file.
   For observation use [measurement](references/measurement.md). These use the same existing
   Marketer browser and lease; never create another login/profile to parallelize.
4. After saving, run [saved-draft QA](../qa-marketer/references/saved-draft.md).
   Changed text invalidates the affected acceptance and upload approval.
5. Report actual completion and unresolved evidence. A manuscript path alone
   does not complete service-draft work. Never mark an uncertain save as done.

Work through `specialist_call(kind="work")` for production and multi-turn peers.
Retain target/conversation identity on resume. A failed or unknown transport is
not proof the peer did nothing; inspect `specialist_session` before deciding
the next action, never switch transports and submit duplicate work.
