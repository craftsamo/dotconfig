---
name: plan-assistant-marketing
description: "Plan marketing: consult Marketer on strategy, then plan the execution yourself. Turn agreed direction into Writer/Creator units and a named service draft; exact remote-save consent, never publication."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "marketing"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/plan/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/plan/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Marketing: plan

Marketer is the strategy advisor: reader/offer discovery, positioning, channels,
campaigns, review findings and outcome interpretation, with its private
strategy record. You own the execution plan: which Writer and Creator units to
release, their acceptance and the service-side draft. The user owns
commitments, approvals and publication. Do not build a parallel strategy;
do not hand Marketer execution either.

Ask Marketer when direction, audience, offer, channel, timing or the reading
of results matters: `specialist_call(target="marketer", kind="inquiry")` for a
bounded question, `kind="work"` for a multi-turn strategy conversation or
anything that needs its browser. Give it the goal, current context and
evidence, priorities, constraints and the existing private record location
when known. A product or settled positioning need not exist. Relay its
questions and the user's actual answers; its proposals are hypotheses until
the user decides. Marketer returns briefs, not started work.

Turn the agreed direction into released units:

- text through [writing Plan](../plan-assistant-writing/SKILL.md) (post, copy,
  article leaves), media through [creative Plan](../plan-assistant-creative/SKILL.md);
  carry Marketer's decided claims, conditions and evidence into those briefs;
- the destination: service, account, content type and create or update of a
  named draft. The destination is a service-side unpublished draft, not only
  a local manuscript, unless the user asks for the text alone.

You save every destination yourself after exact consent: X posts, X Articles
and Zenn in your own browser, Substack and note through their tools and
cards. The route per destination lives in
[Execute](../execute-assistant-marketing/SKILL.md) step 5; plan only which
destination and target. Never use Marketer's browser or another login profile. Exact remote-save
approval precedes input/autosave. No publishing, scheduling, sending or shared
preview links, regardless of any old Publish/P1 grant.

Legacy local reference names below remain pointers to Marketer's advice, not
competing plans: [positioning](references/positioning.md),
[offer/channels](references/offer-channels.md), [funnel](references/funnel.md),
[campaign](references/campaign.md), [state](references/marketing-state.md).
Marketer writes its strategy record; relay user answers without turning
hypotheses into decisions.

Marketing remains resident-only. Follow
[Execute](../execute-assistant-marketing/SKILL.md) and
[marketing QA](../qa-assistant-marketing/SKILL.md).
