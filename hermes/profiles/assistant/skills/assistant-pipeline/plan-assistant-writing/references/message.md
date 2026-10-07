# Message — decision surface

Writer type `message` · QA `prose`. Use `write-message`, `edit-message` or
`analyze-message` for email, chat, notification, UI and error wording.
Social posts use `post.md`; promotional mail uses `copy.md`. The distinction
is the job's purpose, not length or the fact that it uses an email channel.

## Select and scope the work

- Write: supply the recipient role, purpose and channel. A reply needs the
  relevant received text and intended response where those change the wording.
  Let Writer infer fields already answered, not interview the user again.
- Edit: supply the original and named changes, including any authorized new
  stance. Tone/length edits otherwise preserve the original decision and
  commitments, protected fields, variables and quoted material.
- Analyze: supply the actual message and question. Describe/review/compare
  returns observations, not an unsolicited reply. Compare needs both inputs.
  Do not demand a complete writing brief for a bounded tone question.

Name the actual text artifact and constraints, not an action to send it. An
outline/piece/whole job follows the existing release discipline. A short message
does not need an invented outline ceremony or a fixed number of alternatives.

## Relevant context, not private-data expansion

The requester owns identity/context resolution and the decision being expressed.
Chat's message-reply procedure (`chat-assistant/references/message-reply.md`)
can still supply scoped interpretation and reply help; this family does not
replace its People/Project permissions.
When releasing Writer work, pass only the necessary sanitized context and the
user's actual stance. Do not require that personal workflow for every message
or forward raw registry records to Writer. Writer does not perform contact
lookups, infer personal relationships or decide whether the user agrees.

An accept/decline/defer decision cannot be inferred from "make it friendly".
Clarify consequential missing intent. State-dependent notification/UI/error
text needs known state and available actions only to the extent relevant.
Unknown completion must not become "not sent" or "not charged"; a retry
control does not establish safe repetition. Never invent a recovery path.

## Output and acceptance

Drafts are complete text files, not dispatched messages. Subject/body or named
UI fields must be distinguishable from labels and review notes so consumers
cannot send production metadata. Preserve identifiers/placeholders and existing
language preferences supplied by the requester. Style examples are not facts
or authorization for an apology, admission or promise.

Use served criterion evidence: checked / unmet / unverified, not four legacy
passes or lint. Humanizer is explicit-request only. Review stance, known state,
scope and the actual recipient-facing text; sending, code/i18n integration and
rendering remain outside Writer's authority. A permitted short analysis may
be returned in the reply; it is not a draft ready for sending.
