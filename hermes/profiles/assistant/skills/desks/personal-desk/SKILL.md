---
name: personal-desk
description: >-
  Assistant-owned desk for recurring personal operations that should complete inline:
  household-budget records and reports, People registry maintenance, message interpretation
  and reply drafting, and personal docs/data under ~/Workspaces/Personal or
  ~/Workspaces/Projects/Personal. Use in the pinned Personal Telegram topic.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [assistant, desk, personal, household-budget, people, message-reply, inline]
    category: desks
---

<Goal>

Be the stable Personal work surface. Finish routine personal-data work in the Assistant
session, with durable state held by the workspace stores and files rather than chat history.

</Goal>

<OrchestrationOverride>

The chat-wide `orchestration` skill remains active, but this desk narrows its routing:

- A request handled by this skill fixes the execution shape to **inline**.
- If the underlying work needs a `single`, `chain`, or `planned` Worker shape,
  stop in this topic. Preparing the <SpinOut> handoff is the inline result.
- Never call `kanban_create`, `delegate_task`, or another worker-dispatch path from this topic.

</OrchestrationOverride>

<Scope>
<UseWhen>

- Record, review, validate, or report household finances.
- Look up or maintain people, contacts, relationships, and communication preferences.
- Interpret an incoming message and draft a reply for the user to send.
- Read or update `~/Workspaces/Personal/<Group>/{data,docs}`.
- Read or update personal-facing `data/` or `docs/` under
  `~/Workspaces/Projects/Personal`.

</UseWhen>

<DoNotUseWhen>

- The request requires a worker, a kanban card, sustained implementation, or long-running
  research. Keep this topic inline; ask the user to open a new topic for that work.
- Editing code or repositories under `~/Workspaces/Projects/Personal/github/`.
- Sending a drafted message or exporting personal data externally without explicit approval.

</DoNotUseWhen>
</Scope>

<Routing>

Load exactly the relevant depth skill with `skill_view` before acting:

| Request | Skill | Operation |
| --- | --- | --- |
| Receipts, expenses, reimbursements, subscriptions, budget reports | `household-budget` | Follow its `hb` workflow; the SQLite ledger is authoritative |
| Person/contact lookup or maintenance | `people` | Follow its `pp` workflow; never hand-edit its DB |
| Interpret or reply to an incoming message | `message-reply` | Resolve People/project context, draft only, never send |
| Create a new Personal group | `scaffold` | Use its Personal group path; never initialize git there |
| Personal `docs/` or non-registry `data/` | none | Read local `AGENTS.md`, then edit the smallest relevant file directly |

If a request spans domains, load each needed depth skill and follow their cross-store CLI
contract. Never open a sibling skill's database directly.

</Routing>

<WorkspaceRules>

- Read `~/Workspaces/AGENTS.md` and the closest nested `AGENTS.md` before file work.
- `~/Workspaces/Personal/**` and personal-facing content in
  `~/Workspaces/Projects/Personal/{docs,data}` are sensitive. Summarize; never dump raw
  financial records, contacts, or PII into chat, logs, or a <SpinOut> handoff.
- `~/Workspaces/Projects/Personal` is a Projects group despite its name. Its `docs/` and
  `data/` may be handled here, but repository/code work spins out to a new topic.
- Use the owning CLI for canonical stores (`hb`, `pp`, `pj`); direct edits are only for
  ordinary docs/data not governed by a store.
- Ask before destructive changes or external sends. Never send a drafted reply automatically.

</WorkspaceRules>

<SpinOut>

This pinned topic is an Assistant desk, not a worker thread. Do not create or dispatch a
kanban card here. If the work needs delegation, implementation, durable multi-stage execution,
or substantial external research:

1. Complete any safe desk operation already requested (for example, record the project/person
   identity or save a short brief).
2. Summarize the handoff context in a compact, reusable block.
3. Ask the user to open a new Telegram topic and paste or reference that block there. The new
   topic inherits the chat-wide `orchestration` skill and owns any kanban dispatch.

</SpinOut>

<Done>

Report the operation performed and the durable store/file updated. Keep sensitive values
summarized, and leave the desk ready for `/new` without losing required state.

</Done>
