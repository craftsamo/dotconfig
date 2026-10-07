---
name: analyze-marketer
description: >-
  Analyze marketing: collect and interpret measured outcomes. Recommend the
  next decision from comparable evidence; not artifact review, content
  creation or automatic changes.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [analyze, marketing]
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
X result analysis and X conversation discovery also read
[X ranking](../references/x-ranking.md).
Instruction reads do not authorize browser work. Any actual browser page,
including a dashboard read, follows [browsing](../references/browsing.md) and
its lease.

</ReadBeforeWork>

# Analyze outcomes

Start from the question, agreed purpose and actual observations. Load
[state](../references/state.md) and collect what is missing through
[measurement](references/measurement.md). Analysis is an entry mode, not a
requirement to create another campaign.

1. Establish data health first: zero, unavailable, failed retrieval and a
   non-comparable measurement are different. Check period, denominator, source
   definition and changes in distribution/content. Do not explain a broken
   collector as an audience preference.
2. Describe what happened before interpreting why. Separate reach, continuing
   readership, conversation, inquiry and purchase. Avoid adding audiences into
   unique people or attributing every sale to the last clicked post.
3. Compare like with like where possible. Sparse data remains inconclusive;
   natural before/after changes are not causal proof or a randomized A/B test.
   No universal sample count, two-week window or two-success promotion rule.
4. Identify plausible explanations, contradictory evidence and what would
   distinguish them. A reader question is not willingness to pay; a small sale
   can be informative without proving a scalable market.
5. Recommend the few actions worth taking: continue, change, stop, observe or
   improve measurement. Zero changes is legitimate. State evidence, uncertainty,
   scope, burden and a useful review point, not ritual KPIs for every interaction.
6. Record the client's decision and context. Preserve rejected alternatives and
   reasons. A failed trial is not a permanent prohibition, and one success is
   not a universal playbook. Conditions and contradictory evidence survive reuse.

For an offer-unknown client, connect repeated reader needs with actual delivery
capacity through [discovery](../plan-marketer/references/discovery.md). Respect their priority among
products/services, paid content, relationships and enjoyable work. Do not create
sales promises or stronger public claims from this analysis.

For X, start from the `x` tool's `insights` over the snapshot ledger, compare
posts at equal age and read the limits in [X ranking](../references/x-ranking.md):
public counts are not the ranking score, and a format or hour difference over
a few posts is a hypothesis for the next experiment, not a rule.

A requested weekly review can follow these steps, but no cron or automatic
start is implied. Changing thresholds, budgets or starting experiments is the
user's decision and the client's execution; recommend, never start them.
Quality acceptance and a saved draft are not performance success; report these
as separate outcomes.
