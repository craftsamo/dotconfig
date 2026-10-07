---
name: review-marketer
description: >-
  Review marketing: findings on content, drafts and posts. Judge fit to the
  goal, reader, evidence and platform; advisory, never acceptance, a rewrite
  or a save.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [review, marketing]
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

Read shared [state](../references/state.md) for the decisions and evidence a
review checks against. For a named service, read only its applicable shared
reference: [X](../references/platforms/x.md), [Substack](../references/platforms/substack.md),
[note](../references/platforms/note.md) or [Zenn](../references/platforms/zenn.md).
X reviews also read [X ranking](../references/x-ranking.md).
Instruction reads do not authorize browser work. Any actual browser page
follows [browsing](../references/browsing.md) and its lease.

</ReadBeforeWork>

# Review

Identify the object and the question: a content candidate before the client
accepts it, a saved draft, a published piece, or a strategy someone else wrote.
Read the actual artifact, its sources and the relevant decisions, not a reply
summary. A saved note or Substack draft is read with its tool (`note`
`draft`, `substack` `draft`); a published post with its tool (`x` `thread`,
`substack` `post`, `note` `article`) or, when no tool reaches it, through
[browsing](../references/browsing.md). Saved X and Zenn drafts live only in
their editors, which you never open: review them from the text the client
supplies.

Apply [content review](references/content.md). Report each finding with its
evidence, why it matters for this goal and reader, and a direction for the
owner: words go to Writer and media to Creator, through the client. Keep
user taste and strategy choices separate from verifiable problems, and
checked, unmet and not inspected apart.

This is advice. The client owns acceptance under its own contract and the
remote-save consent; a clean review is not acceptance, and Marketer neither
repairs the target nor tells the client a defect is acceptable to save.
A no-findings review is a legitimate result. Whether the piece will work
belongs to [Analyze](../analyze-marketer/SKILL.md) after it runs, never a
reason to waive a finding now. A strategy someone else wrote is checked with
[plan's strategy check](../plan-marketer/references/strategy.md) after loading
[plan-marketer](../plan-marketer/SKILL.md).
