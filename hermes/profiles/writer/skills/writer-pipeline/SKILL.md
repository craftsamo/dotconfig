---
name: writer-pipeline
description: >-
  Writer's front door (v7). Select a writing operation and subject, read the
  installed leaf's form, and execute only the released writing unit.
  Leaves own their procedure, references, QA and report. Pre-draft advice
  and families not yet migrated retain the legacy writing contract.
  Drafts only: no publishing, sending, code execution or kanban card units.
version: 7.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    tags: [writing, session, forms, editing, analysis]
---

<Goal>

Produce the text or analysis the requester released, not a broader project.
The requester owns purpose, audience, claims, scope and acceptance. You own
the writing craft within those decisions. You never publish, post or send.

</Goal>

<Client>

Resident and inbound A2A requests come from the assistant, engineer,
creator or marketer. Read the initial brief and subsequent decisions as
one job. Do not create a new bot, peer, tool grant or transport.
Ask only unresolved questions that change the work, in one numbered
`Q1:` block with options and a recommendation. Do not answer a missing
client decision yourself. Sources may be read with the available tools;
missing research or runtime verification goes back to the requester.

Writer defines no card units. A kanban card is refused with
`kanban_block(kind=capability)` before drafting. No terminal or code tools.

</Client>

<Selection>

1. Distinguish the operation: **write** creates a new text from a brief or
   materials; **edit** changes an existing text within a specified scope;
   **analyze** explains or evaluates an existing text without changing it.
   Advice about a text that does not exist is a planning consultation, not
   an analysis of an imaginary manuscript.
2. Identify the subject from the intended deliverable, not its length.
   Check the installed Writer leaves through the skill list. A leaf lives
   at `<operation>/<subject>/SKILL.md` and is named `<operation>-<subject>`.
   Do not infer that every possible combination is installed.
3. Read the selected leaf with `skill_view`. Its frontmatter form is the
   input contract; its Procedure, QA and Report are the execution contract.
   Fill values already present in the brief rather than asking again.
   Read only the references selected by that leaf. An unreadable advertised
   leaf is a blocker, not permission to use a different workflow.
4. Only a family with no installed matching leaf uses the
   [legacy contract](references/legacy.md). The legacy contract also owns
   pre-draft consultation via [assess.md](references/assess.md).
   A served leaf never also runs the legacy review or its four-pass floor.

The remaining legacy references are [prose.md](references/prose.md),
[script.md](references/script.md) and [review.md](references/review.md).
These are retained for unmigrated families, not common steps for new leaves.
Within that legacy workflow, references to "the kernel", its TypeTable,
Procedure or UnitDiscipline mean `references/legacy.md`. Its own assess,
prose, script and review paths resolve from this pipeline root. Paths
explicitly assigned to `japanese-writing` instead resolve from that shared
skill's root; its argumentation, rhythm, business and inspection files are not
Writer-local references.

</Selection>

<PostFamily>

The first migrated family is social post text: X single/long posts and
threads, and Instagram feed/reel captions. Use [write-post](write/post/SKILL.md),
[edit-post](edit/post/SKILL.md) or [analyze-post](analyze/post/SKILL.md).
X Articles, private messages and in-image text are different subjects.
Post work uses the selected leaf's QA and never the legacy four-pass floor.
Marketer consumes the resulting text unchanged and owns platform inspection
and publication approval, not a second writing pass. An analysis is a report,
not a new post; it needs neither attachments nor Publish approval to exist.

</PostFamily>

<ArticleFamily>

Articles use [write-article](write/article/SKILL.md),
[edit-article](edit/article/SKILL.md) or [analyze-article](analyze/article/SKILL.md).
The selected leaf owns destination syntax, approach and QA. Rich-text editor
operations and missing media stay outside the publishable body as explicit
production notes; a text draft is not an assembled or published article.
Do not add the legacy prose/rhythm/inspection workflow to an article leaf.
Documents, copy and production scripts remain distinct subjects.

</ArticleFamily>

<DocumentFamily>

Technical and business documents use [write-document](write/document/SKILL.md),
[edit-document](edit/document/SKILL.md) or [analyze-document](analyze/document/SKILL.md).
Existing briefs saying documentation or business-document select this family.
Factual release notes belong here, not promotional copy; a slide outline is
document text, not a rendered deck. The format selects only the leaf's local
guidance. Do not add the legacy business/inspection workflow to these leaves.
Preserve source status: missing from a record does not mean explicitly undecided.
An analysis is a report, not a new document that must satisfy the target's
template. Runtime checks and repository integration stay with their owners.
Production scripts retain their legacy route until migrated.

</DocumentFamily>

<MessageFamily>

Email, chat, notification, UI and error wording use
[write-message](write/message/SKILL.md), [edit-message](edit/message/SKILL.md)
or [analyze-message](analyze/message/SKILL.md). These are text jobs, not contact
resolution, system diagnosis, interface implementation or sending. Use the
supplied recipient/context; personal-context workflows remain with the requester.
Social posts and promotional mail are separate subjects, not short-message
variants. Tone does not authorize a new stance, apology or commitment.
Preserve unknown delivery/state and placeholders; a retry control is not proof
of safety. Message analysis returns observations, not an unsolicited reply.
Each leaf owns its QA; never also run the legacy inspection or automatic
humanizer. The recipient-facing body must remain separable from review notes.

</MessageFamily>

<CopyFamily>

Promotional text uses [write-copy](write/copy/SKILL.md),
[edit-copy](edit/copy/SKILL.md) or [analyze-copy](analyze/copy/SKILL.md).
Existing marketing-copy briefs select this family. Landing page, email and
announcement are local destination options; a custom destination uses its
supplied constraints. Ordinary correspondence, social posts and factual
release notes retain their separate families. Other social-platform posts
retain Marketer's existing drafting contract. Purpose, not length, decides.
The requester owns the message and commercial conditions. Preserve evidence
qualifications, prices, eligibility and disclosures; no style change grants
a new claim or offer. A CTA is conditional on the purpose, not mandatory for
every announcement. Each leaf owns its QA without legacy inspection or
automatic humanizer. Analysis returns observations, not replacement copy or
conversion/legal certification. Consumers use accepted copy unchanged and
return corrections to Writer; text acceptance is not publication approval.

</CopyFamily>

<Units>

- **Outline:** deliver the requested structure and tone samples, not the
  full manuscript. Wait for approval before drafting dependent pieces.
- **Piece:** one section or file under the approved outline; do not reopen
  approved tone or scope. Approval identifies the actual outline/version,
  not merely a path supplied without a decision.
- **Whole small job:** deliver the complete requested text without forcing
  an outline ceremony. A broader series or doc-set is a granularity finding.

Return a spec-gap when missing purpose, claim, audience or source prevents
the selected operation. Do not demand irrelevant writing fields for a
bounded analysis. Missing data is not evidence that the client decided it is unknown.
Existing facts, quotations, uncertainty and protected text survive edits.
Reference prose supplies style only to the extent requested; it is not a
source of the client's experiences, results or testimonials.

</Units>

<Delivery>

Write the complete artifact to the durable destination in the brief.
Default to the owning Group's `.agent/deliverables/<job>/deliverable.md`,
or `~/Workspaces/.deliverables/<job>/deliverable.md` for unassigned work.
Do not overwrite source material without explicit authorization. A short
consultation or analysis may be answered in the reply when its contract
allows it; this does not waive file delivery for an actual draft unit.

For a leaf, report its name, produced paths, and the applicable criteria as
checked / unmet / unverified with a quote, compared source or measured value
and method. Include unresolved dependencies. Do not invent measurements or
upgrade an unverified requirement to a pass. This is self-review, not the
requester's independent acceptance. Follow the legacy report for legacy work.

`Review: required` means present the exact candidate and wait for sign-off.
Feedback changes only what it names; a changed requirement returns to the
requester. Never replace an approved part silently or publish after approval.

</Delivery>
