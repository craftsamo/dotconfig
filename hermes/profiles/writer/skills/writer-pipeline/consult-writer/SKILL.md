---
name: consult-writer
description: >-
  Writer advice before drafting: format, structure and voice. Recommend scope,
  inputs and tradeoffs for a future text. Not a released outline or full draft,
  editing or evaluating an existing target, requester acceptance or publishing.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    tags: [writing, consultation, planning]
    output: "Brief advice with reasons, assumptions and unresolved inputs; not a production artifact"
---

<ReadBeforeWork>

When executing this consultation as Writer, require the full `writer-pipeline`
kernel and this entry in the current context. Load a missing kernel with
`skill_view(name="writer-pipeline")`; a past load or summary is not its body.
Re-evaluate the operation, subject and selected detail references on each turn
and before a scope-changing action. Reuse bodies still present; reading does
not restart a released unit, expand a grant or replace protected text.
If `skill_view` returns unchanged without the earlier body, use `read_file` on
`${HERMES_SKILL_DIR}/../SKILL.md` for the kernel or on this entry's canonical
document. Follow `next_offset` to complete a truncated read; never evade dedup
with alternate paths or artificial ranges. If a required body remains
unavailable, stop the affected action and report it.
A Client reading this contract for briefing does not execute the consultation
or inherit Writer's role. Selected production forms/references inform advice
only; reading them does not release their drafting, editing or analysis work.

</ReadBeforeWork>

# Pre-draft consultation

Use when the requester wants advice about a future text: which format, scope,
structure or voice would serve the goal, and which inputs writing would need.
This is planning input, not a fourth writing operation or permission to draft.

1. Identify the decision the requester needs, the audience/purpose and the
   materials already provided. Distinguish reference examples from a target to
   edit or analyze. Ask only when the missing answer materially changes the
   recommendation; label assumptions instead of manufacturing facts.
2. Consult an installed candidate leaf's form and relevant local references
   only when they inform that decision. Do not execute its drafting procedure
   or require every writing field for a bounded planning question. An unknown
   format/capability is an explicit gap, not a generic fallback or a new skill.
3. Recommend a shape and explain the tradeoff. Give a short outline or an
   illustrative fragment only when useful to the question; no full draft or
   unsolicited rewrite. Do not force a fixed number of sections or tone samples.
   The requester decides scope and taste; your recommendation is not approval.
4. Separate constraints from proposals. A suggested length, panel count or
   speaking pace is not an actual producer limit or measured timing. Read
   supplied consumer requirements rather than inventing them. Unsupported
   claims, missing evidence and unfinished media remain named dependencies.
   For effort/sizing questions, propose an approximate length or work breakdown
   and the needed inputs, with assumptions. These are planning estimates, not
   measured completion times, provider costs or approval to release more work.
5. Check that the advice answers the question, preserves provided facts and
   distinguishes assumptions from evidence. Report the recommendation, its
   reasons, requested sizing and decisions/inputs still needed, briefly in the reply. Do not
   claim a draft file, independent acceptance, publication or production result.

An explicitly released outline unit is different: route to the appropriate
write leaf and deliver the requested outline artifact under its contract.
If asked to edit or evaluate an existing target, return to the kernel's
operation selection and use the corresponding edit/analyze leaf. Reference
text supplied merely to inform advice does not itself change the operation.

For Japanese examples use `japanese-writing` as language knowledge only.
No lint, naturalness score, required humanizer or repeated review loop applies
to this consultation. No terminal, media production or publishing authority is
added, and a planning reply is never handed to a producer as approved text.
