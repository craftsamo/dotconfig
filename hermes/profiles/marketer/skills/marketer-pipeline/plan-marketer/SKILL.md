---
name: plan-marketer
description: >-
  Plan marketing: audience, offer, channels and campaigns. Agree direction and
  evidence with the client; not content production, browser saving or results
  analysis.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [plan, marketing]
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

# Plan

Start from the requested decision, existing decisions and available evidence.
The deliverable may be advice, an alternative, a campaign or a released content
unit; it need not be a complete marketing plan. Read [state](../references/state.md) before
creating or resuming durable work. If the human names no existing record, agree
on a private job/project location; do not demand an Assistant-supplied ledger.

1. Establish the desired outcome, current situation and constraints that could
   change the answer. Preserve supplied priorities and non-goals. Ask only the
   unresolved consequential question, with realistic alternatives and a default.
2. Select the relevant procedure: [discovery](references/discovery.md) for unknown audience
   or offering; [positioning](references/positioning.md) for who/why; [offer](references/offer.md) for
   what to provide; [channels](references/channels.md) for where/how to reach people;
   [campaign](references/campaign.md) for a bounded execution plan.
3. Gather enough evidence to choose a next action. Delegate substantive research
   through [parts](../build-marketer/references/parts.md). Separate public market observation from
   permission to open an authenticated account or upload private material.
4. Propose the smallest useful action and its reason, cost/time shape, unknowns
   and relevant stopping condition. Use [strategy QA](../qa-marketer/references/strategy.md).
   Do not invent a forecast merely to fill a template.
5. Record the user's decision where required. Release only the agreed work to
   [Build](../build-marketer/SKILL.md). Strategy approval does not authorize paid generation,
   service uploads, draft replacement, publishing or recurring jobs.

Marketer owns these proposals even when Assistant is the client. Assistant may
relay constraints and approval; it is not a second strategist. A price, offer
term or delivery commitment is a proposal until explicitly decided by the user.
For direct-human work the same evidence and approval requirements apply.

Consultation may finish in the reply. Critique reports evidence-anchored findings
without repairing its target. For a consequential decision, test the strongest
counterargument and alternatives; do not stage a named-person council or invent
agreement among simulated experts.
