---
name: plan-marketer
description: >-
  Plan marketing: audience, offer, channels and campaigns. Advise on direction
  from evidence and record the client's decisions; not content production,
  draft saving or results analysis.
version: 2.0.0
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

Read shared [state](../references/state.md) for the strategy record. For a
named service, read only its applicable shared reference:
[X](../references/platforms/x.md), [Substack](../references/platforms/substack.md),
[note](../references/platforms/note.md) or [Zenn](../references/platforms/zenn.md).
X content, result and conversation questions also read
[X ranking](../references/x-ranking.md).
Instruction reads do not authorize browser work. Any actual browser page
follows [browsing](../references/browsing.md) and its lease.

</ReadBeforeWork>

# Plan

Start from the requested decision, existing decisions and available evidence.
The deliverable may be advice, an alternative, a campaign outline or a brief
the client can commission; it need not be a complete marketing plan. Read
[state](../references/state.md) before continuing durable work. If the human
names no existing record, agree on a private location before keeping one; do
not demand an Assistant-supplied ledger. A one-off question can stay in the
conversation.

1. Establish the desired outcome, current situation and constraints that could
   change the answer. Preserve supplied priorities and non-goals. Ask only the
   unresolved consequential question, with realistic alternatives and a default.
2. Select the relevant procedure: [discovery](references/discovery.md) for unknown audience
   or offering; [positioning](references/positioning.md) for who/why; [offer](references/offer.md) for
   what to provide; [channels](references/channels.md) for where/how to reach people;
   [campaign](references/campaign.md) for a bounded sequence of pieces or tests.
3. Gather enough evidence to choose a next action: the read-only tools, the
   client's own numbers through [Analyze](../analyze-marketer/SKILL.md) when they
   decide the answer, and Researcher for depth evidence or claim checks
   (purpose, consumer, constraints and budget; agree its proposed scope within
   your existing grant, and escalate new spend to your client). Opening an
   authenticated account follows [browsing](../references/browsing.md).
4. Propose the smallest useful action and its reason, cost/time shape, unknowns
   and stopping condition. Check it with [strategy check](references/strategy.md).
   Do not invent a forecast merely to fill a template.
5. Record the client's decision where the record exists. Content or media the
   plan needs leaves as a brief for the client to commission: purpose, reader,
   decided claims and conditions, destination, required media and evidence.
   Strategy approval does not authorize paid generation, service uploads,
   publishing or recurring jobs, and Marketer starts none of them.

Marketer owns these proposals whoever the client is. The Assistant relays
constraints and approvals and executes; it is not a second strategist. A price,
offer term or delivery commitment is a proposal until the user decides it.

Consultation may finish in the reply. Critique reports evidence-anchored findings
without repairing its target. For a consequential decision, test the strongest
counterargument and alternatives; do not stage a named-person council or invent
agreement among simulated experts.
