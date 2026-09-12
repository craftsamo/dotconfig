---
name: analyze-message
description: >-
  Describe, review or compare existing email, chat, notification, UI or error
  wording using the actual text and supplied context. Distinguish expressed
  intent from guesses about the sender or recipient. Return observations,
  not a reply draft, system diagnosis, contact investigation or sent message.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Message analysis with anchored observations, interpretation and unknowns; original unchanged and no message sent"
    form:
      source: {required: true, type: text, label: "Existing message text, local path or readable URL"}
      question: {required: true, label: "What the requester wants explained or checked"}
      mode: {required: false, options: [describe, review, compare], label: "Infer from the question; description need not identify defects"}
      focus: {required: false, type: text, label: "One or more aspects: stated intent, tone, ambiguity, commitments, state claims or action guidance"}
      channel:
        required: false
        options: [email, chat, notification, ui, error]
        other: true
        references: references/*.md
        label: "Infer from the target; needed only for channel-specific assessment"
      context: {required: false, type: text, label: "Relevant exchange or screen context; unavailable context limits conclusions"}
      criteria: {required: false, label: "Known recipient, purpose, stance and constraints when evaluating fit"}
      compare_with: {required: false, type: text, label: "Comparison text/path/URL; required for compare"}
      sources: {required: false, type: text, label: "Supplied evidence for factual/state checks, not permission to inspect registries or systems"}
      language: {required: false, label: "Report language; default to the requester's language"}
      length: {required: false, label: "Requested analysis depth or report length"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit analysis guidance only, never permission to rewrite"}
      note: {required: false, type: text, label: "Other analysis constraints"}
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

1. Read the actual target and question. State which context is available;
   missing context is not proof of intent, blame or a relationship. Do not
   query contacts or private registries. A missing message goes back to the
   requester; pre-draft advice is consultation, not fabricated analysis.
2. Choose describe/review/compare from the question. Read both inputs for a
   comparison and compare like aspects. Do not require a full writing brief
   for a bounded tone question. If channel criteria matter, read only
   [email](references/email.md), [chat](references/chat.md),
   [notification](references/notification.md), [UI](references/ui.md) or
   [error](references/error.md). Custom channels retain supplied constraints.
3. Quote the words supporting a reading of the message. Separate explicitly
   expressed requests, commitments and uncertainty from possible implications
   or reader reactions. Do not claim to know how the recipient feels, diagnose
   the sender, or assign unstated motives. Description need not find defects.
4. For state/action wording, distinguish what the message asserts from what
   supplied evidence establishes. A timeout does not prove non-delivery or
   retry safety. Do not test an action, inspect a real system or manufacture
   a missing screenshot. An unseen interface limits layout/interaction claims,
   not every textual observation.
5. Use `japanese-writing` for Japanese wording observations, without retired
   legacy workflows or statistical scoring. `humanizer` is explicit-only and
   gives observations, not a rewritten message. Do not quote private details
   beyond what the analysis actually needs or leak secrets into its report.
6. Apply QA to the analysis report, then return a permitted short report in
   the reply or save it at the requested durable path. Keep the source unchanged.
   Do not compose an unsolicited reply, change a system or send anything.

</Procedure>

<QA>

- Substantive observations identify the relevant text and answer the question
  within the read scope. Interpretations and unknowns are not stated as facts.
- A comparison uses both inputs; a description need not rank variants or
  invent faults. Claims about intent or likely effect remain bounded by context.
- A message's assertion is not independently verified system state. Actual
  delivery, retry safety, interface fit and recipient reactions remain
  unverified without corresponding evidence. No fabricated measurements.
- Evaluate this report, not an imaginary new message: it needs no new greeting,
  apology, requested action, button label or replacement reply. The original
  and supplied context remain unchanged; analysis grants no sending authority.
- Use checked / unmet / unverified evidence and minimum necessary quotations.
  Do not emit naturalness scores, author detectors or a legacy pass receipt.

</QA>

<Report>

Name `analyze-message`, target, read scope, mode and relevant channel. Provide
anchored observations and requested recommendations with applicable evidence
and limitations. Do not deliver a replacement message or claim the recipient's
actual reaction, successful delivery, a system diagnosis or a sent reply.

</Report>
