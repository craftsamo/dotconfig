---
name: plan-assistant-engineering
description: "Plan engineering: frame outcomes for Engineer proposals. Clarify Client constraints and implementation approval, not technical decomposition or automatic Issue management."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "engineering"]
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

# Engineering - Client planning

You are Engineer's Client, not a second technical planner. Supply purpose,
constraints, known decisions, target repository and observable success criteria.
Engineer uses OpenCode to investigate and propose the technical plan. Do not
start a separate OpenCode planning session or pre-decompose its implementation.
An existing Issue or plan is useful context, not a required intake artifact.

1. Establish what the user wants changed or learned, and what must remain intact.
   Locate an existing repository through the workspace registry when available;
   do not demand paths or technical choices already known in the conversation.
2. Read the relevant Client guide below. Ask only consequential unresolved
   questions; Engineer can investigate technical feasibility and recommend
   architecture, tools, sequencing and verification.
3. Request planning through the Engineer resident conversation. Relay constraints
   and prior decisions accurately, without labeling a suggestion as user approval.
4. Present the proposed outcome, scope, important tradeoffs and risks. Obtain
   explicit implementation approval for the agreed plan. Planning consent alone
   does not authorize implementation. A small settled fix needs no large ceremony.
5. Release the approved scope through PR delivery under
   [Execute](../execute-assistant-engineering/SKILL.md). Do not gate every internal phase.

Issue management is explicit-only: ask Engineer to create/update Issues only
when the user requested tracking this job that way. A supplied Issue URL is a
specification, not permission to edit it. Duration, complexity or multiple PRs
never create an automatic Issue/epic/Projects requirement. Existing session IDs
can be handed over as context, but old grants need reconciliation, not adoption.

## Client guides

| Archetype | Guide |
| --- | --- |
| A repository needs to be established | [bootstrap.md](references/bootstrap.md) |
| Content-led site, landing page, blog or portfolio | [web-content.md](references/web-content.md) |
| Stateful Web application | [webapp.md](references/webapp.md) |
| Script, CLI or automation | [tool.md](references/tool.md) |
| Existing-repository change | [existing-change.md](references/existing-change.md) |

These guides hold Client questions and acceptance expectations, not prescribed
implementation units. Engineer owns technical planning and UI/UX verification.
Planning, diagnosis or review may finish with an answer and no code or PR.
