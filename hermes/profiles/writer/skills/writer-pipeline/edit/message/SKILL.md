---
name: edit-message
description: >-
  Edit an existing email, chat reply, notification, UI text or error message
  within the requested scope. Preserve intent, commitments, state uncertainty
  and placeholders. Not analyzing only, composing from an absent original,
  sending messages, changing an interface or editing translation files.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised message draft with changed fields/scope and unresolved checks; source not overwritten without authorization"
    form:
      source: {required: true, type: text, label: "Original message text, local path or readable URL"}
      changes: {required: true, label: "Requested wording, tone, length or content changes"}
      scope: {required: false, options: [wording, structure, rewrite], label: "Default wording; broader changes require explicit authorization"}
      channel:
        required: false
        options: [email, chat, notification, ui, error]
        other: true
        references: references/*.md
        label: "Infer from the original; preserve unless a channel change is requested"
      recipient: {required: false, label: "Recipient role/relationship where needed; do not look up personal records"}
      context: {required: false, type: text, label: "Relevant prior exchange or screen context supplied by the requester"}
      stance: {required: false, label: "An explicitly requested new position; otherwise preserve the original intent"}
      action: {required: false, label: "Authorized changes to the requested action, destination or deadline"}
      state: {required: false, label: "Evidence-backed correction to a system/event state; no inferred outcome"}
      available_actions: {required: false, label: "Known controls or recovery steps relevant to this edit"}
      sources: {required: false, type: text, label: "Evidence for factual corrections or additions"}
      language: {required: false, label: "Keep the original language unless specified"}
      tone: {required: false, label: "Keep the original voice unless a change is requested; tone does not authorize new commitments"}
      style_reference: {required: false, type: text, label: "Expression example, not a replacement intent or factual source"}
      reference_focus: {required: false, label: "What to borrow from the example"}
      must_keep: {required: false, label: "Protected intent, qualifications, subject/body fields, identifiers or placeholders"}
      avoid: {required: false, label: "Requested exclusions; clarify conflicts with protected meaning"}
      length: {required: false, label: "Target or hard bound with units"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other editing or channel constraints"}
---

<ReadBeforeWork>

When executing this leaf as Writer, require the full `writer-pipeline` kernel
and this leaf in the current context. Load a missing kernel with
`skill_view(name="writer-pipeline")`; a past load or summary is not its body.
Re-evaluate the operation, subject and selected detail references on each turn
and before a scope-changing action. Reuse bodies still present; reading does
not restart a released unit, expand a grant or replace protected text.
If `skill_view` returns unchanged without the earlier body, use `read_file` on
`${HERMES_SKILL_DIR}/../../SKILL.md` for the kernel, or the canonical document
under this leaf for its own instructions. Follow `next_offset` to complete a
truncated read; never evade dedup with alternate paths or artificial ranges.
If a required body remains unavailable, stop the affected action and report it.
A Client reading a form or reference for briefing does not execute this procedure
or inherit Writer's role. Read only the detail references selected below.

</ReadBeforeWork>

<Procedure>

1. Read the complete original, named changes and supplied context. A missing
   target is a question, not permission to invent an original. Identify the
   editable fields and protected intent; do not change a refusal to a delay,
   a possibility to a promise, or uncertainty to a definite state for tone.
2. Read only the matching edit reference: [email](references/email.md),
   [chat](references/chat.md), [notification](references/notification.md),
   [UI](references/ui.md) or [error](references/error.md). An inferred or custom
   channel follows actual supplied constraints, not guessed native formatting.
   Public social posts and promotional copy keep their separate owners.
3. Apply the authorized changes. Wording edits do not reopen commitments,
   responsibility or decisions; a requested new stance is kept distinct from
   a style preference. Ask when a correction changes a consequential fact
   without evidence. Source quotations, variables, names and IDs stay exact
   unless their change is explicitly supported and requested.
4. Preserve the known/unknown boundary in notifications and state messages.
   Shortening must not turn "result unknown" into "not sent" or add a retry
   that could duplicate an action. Do not edit an application, verify a real
   transaction or execute a screen instruction to resolve the uncertainty.
5. Use `japanese-writing` as Japanese expression knowledge, not a legacy review
   workflow. Preserve natural wording and the original register unless asked.
   `humanizer` is explicit-only and cannot modify protected meaning. Do not
   import a style example's feelings, experiences, excuses or admissions.
6. Compare the revision with the original, including untouched fields, then
   re-read it in context. Keep body text separate from field labels and review
   notes. Check source-backed wording, placeholders, links and qualifications.
   Private context is used only as needed; never expose secrets in the report.
7. Apply QA and deliver the complete revision to the requested path. Do not
   overwrite the source without authorization or alter a message that is live
   or already sent. A changed approved draft needs renewed approval. Text
   editing never grants authority to send, publish, build UI or update i18n.

</Procedure>

<QA>

- Each change maps to the request; untouched fields and protected text remain
  intact. A politeness edit does not introduce an apology, agreement or promise.
- Intent, negation, conditions, responsibility and uncertain results survive.
  New facts need evidence; an existing control does not establish retry safety.
- Identifiers, placeholders and subject/body boundaries remain usable without
  sending metadata or notes. Known link text is not proof of a working endpoint.
- A text-only revision does not prove delivery, recipient reaction, layout fit
  or implemented behavior. Hard bounds need reliable measurements and methods;
  unmet/unverified required criteria are not claimed complete.
- Report checked / unmet / unverified evidence. Do not add the legacy four-pass
  review, automatic humanizer or statistical quality/authorship scoring.

</QA>

<Report>

Name `edit-message`, channel, original/revised paths and changed fields. Report
applicable evidence and unresolved conditions without unnecessary private data.
Deliver the complete revision, not a fragment or whole draft pasted in the reply.
Do not imply that any message was sent, recalled, published or implemented.

</Report>
