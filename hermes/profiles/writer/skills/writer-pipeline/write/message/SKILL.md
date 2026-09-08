---
name: write-message
description: >-
  Draft an email, chat reply, notification, UI text or error message from
  the intended recipient, purpose and known context. Preserve the sender's
  actual stance and system-state uncertainty. Not a social post, promotional
  campaign, contact lookup, message sending, interface implementation or i18n
  file workflow.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete message draft at the requested path; recipient-facing text separated from field labels and review notes; never sent"
    form:
      recipient: {required: true, label: "Who receives or reads this message; a role or relationship can be enough"}
      purpose: {required: true, label: "What to communicate or request, without inventing the sender's decision"}
      channel:
        required: true
        options: [email, chat, notification, ui, error]
        other: true
        references: references/*.md
        label: "Infer the stated channel; a described custom channel is equally valid"
      context: {required: false, type: text, label: "Relevant received text, prior exchange or screen context; needed when the reply depends on it"}
      stance: {required: false, label: "Intended accept, decline, defer or other position; clarify when it changes the reply"}
      action: {required: false, label: "Requested recipient action and actual deadline/destination, if any"}
      state: {required: false, label: "Known system/event state and what remains unknown; required for state-dependent claims"}
      available_actions: {required: false, label: "Known controls, safe recovery paths or contacts; do not invent an action to fill a message"}
      language: {required: false, label: "Output language; use an explicit supplied preference, otherwise default Japanese"}
      tone: {required: false, label: "Voice in ordinary words, not model temperature or a change of stance"}
      sources: {required: false, type: text, label: "Supplied facts or supporting paths/URLs/excerpts; not authority to inspect private registries"}
      style_reference: {required: false, type: text, label: "Expression example or its path; not the sender's facts, feelings or promises"}
      reference_focus: {required: false, label: "Which aspects of the example to borrow"}
      must_keep: {required: false, label: "Protected intent, qualifiers, identifiers, placeholders, quoted text or wording"}
      avoid: {required: false, label: "Excluded content; clarify conflicts with factual fidelity or protected text"}
      length: {required: false, label: "Target or hard bound with units; no universal channel limit is assumed"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other requirements, including a custom channel's text constraints"}
---

<Procedure>

1. Read the released brief and supplied context. Infer answered fields before
   asking Q<n>. A role can identify the recipient; do not require unnecessary
   personal details. If a reply's accept/decline/commitment is undecided, ask
   rather than choosing it from the requested tone. Use only the provided
   relevant context; do not resolve contacts or query private registries.
2. Read only the selected channel: [email](references/email.md),
   [chat](references/chat.md), [notification](references/notification.md),
   [UI](references/ui.md) or [error](references/error.md). For a custom channel,
   use its stated constraints without coercing it into a listed one or
   inventing formatting support. Social posts and promotional copy are other
   families, even when short or delivered by email.
3. Confirm state and available actions only where needed for the actual text.
   If an operation's outcome is unknown, retain that uncertainty. A timeout
   does not prove failure or non-delivery, and an available retry control does
   not prove repeating the action is safe. Do not invent a recovery path.
4. Draft the released message. An outline unit stops at structure and requested
   samples; an approved piece follows its agreed conditions; a small whole
   message needs no forced outline or variant round. A sequence or campaign
   larger than the released unit goes back for a scope decision.
5. Keep the sender's intended meaning. Politeness or warmth must not add an
   apology, admission, agreement, deadline or promise on the sender's behalf.
   Ground claims in the brief/sources, not a style example. Preserve names,
   quotes, placeholders and conditions exactly when required. Do not insert
   a name, signature or personal experience merely to make the text complete.
6. For Japanese, use `japanese-writing` as expression/notation knowledge only,
   not its retained legacy workflows or lint. `humanizer` is explicit-only
   and cannot override stance, facts or protected content. Keep sensitive
   details and unnecessary private context out of both the body and report.
7. Apply QA and save the complete draft at the requested durable path. Separate
   the actual subject/body or named UI fields from instructions and review
   notes, so a consumer cannot send them as message text. Do not invent HTML
   comment hiding. This is text only: no send, push, live edit, UI build or
   translation-file update. An available screenshot may inform wording, but
   unseen images cannot be claimed as inspected or certify an implemented UI.

</Procedure>

<QA>

- Compare intent, recipient, requested action and context with the actual
  draft. No unauthorized apology, agreement, promise or changed decision.
- Claims, dates, names and conditions trace to supplied information. Unknown
  completion/delivery stays unknown; no unsupported retry-safety or recovery
  guarantee. A source description is not independent runtime verification.
- Preserve placeholders/identifiers and requested wording. Only necessary,
  authorized recipient context is included; reports do not expose secrets.
- Subject/body or UI fields are distinguishable from production and QA notes.
  Known channel constraints are honored, but render/interaction fit and hard
  bounds remain unverified without appropriate evidence and counting method.
- A required check that is unmet or unverified prevents claiming that scope
  complete. Use criterion evidence, not legacy pass counts or a naturalness
  score. This is self-review, never independent acceptance or sending approval.

</QA>

<Report>

Name `write-message`, channel, released unit and draft path. Summarize only
necessary context/choices and applicable checked / unmet / unverified evidence.
State remaining questions or implementation checks. Deliver a file rather than
pasting the whole draft in the reply. The message was not sent or implemented.

</Report>
