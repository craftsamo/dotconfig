---
name: edit-copy
description: >-
  Edit existing landing-page copy, promotional email or an announcement within
  a named scope. Preserve claims, offer terms and disclosures unless their
  correction is authorized and supported. Not analysis only, a new campaign,
  social post editing, live page changes, sending or publishing.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised copy draft with changed scope and unresolved checks; no unauthorized source overwrite or publication"
    form:
      source: {required: true, type: text, label: "Original copy text, local path or readable URL"}
      changes: {required: true, label: "Requested wording, tone, length or content changes"}
      scope: {required: false, options: [wording, structure, rewrite], label: "Default wording; broader changes require explicit authorization"}
      destination:
        required: false
        options: [landing-page, email, announcement]
        other: true
        references: references/*.md
        label: "Infer from the original; preserve unless a destination change is requested"
      audience: {required: false, label: "Approved audience; preserve unless its change is released"}
      message: {required: false, label: "Explicitly authorized message correction; otherwise retain the original claim and its scope"}
      offer: {required: false, type: text, label: "Evidence-backed changes to actual price, eligibility, availability or other terms"}
      action: {required: false, label: "Authorized changes to the action or destination, if relevant"}
      sources: {required: false, type: text, label: "Evidence for factual corrections, additions or disputed existing claims"}
      language: {required: false, label: "Keep the original language unless specified"}
      tone: {required: false, label: "Keep the original voice unless requested; intensity does not authorize stronger claims"}
      style_reference: {required: false, type: text, label: "Expression example, not replacement facts, proof or offer terms"}
      reference_focus: {required: false, label: "What to borrow from the example"}
      must_keep: {required: false, label: "Protected wording, qualifications, disclosures, identifiers and commercial conditions"}
      avoid: {required: false, label: "Requested exclusions; clarify conflicts with protected meaning"}
      length: {required: false, label: "Target or hard bound with units"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other editing or destination constraints"}
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

1. Read the complete original, named changes, brief and available evidence.
   A missing target is a question, not permission to invent an original. Identify
   editable fields and protected wording/conditions. Shortening or increasing
   confidence does not authorize a different promise, offer or audience.
2. Read only the matching edit reference: [landing page](references/landing-page.md),
   [email](references/email.md) or [announcement](references/announcement.md).
   Infer the existing destination; custom formats retain actual constraints.
   Factual release notes, direct correspondence and social posts are not copy
   merely because they announce something or use short persuasive wording.
3. Apply only authorized changes. Check any new or corrected factual assertion
   against supplied evidence. Preserve uncertainty, eligibility, dates, prices
   and disclosures unless their correction is both requested and supported.
   If protected text conflicts with evidence, return that conflict; do not
   quietly delete the qualifier, invent support or claim the old text verified.
4. Reorganization must keep qualifications associated with the claims they
   limit. Check the headline, body, action and terms together, including
   untouched fields. Do not add a CTA, urgency or testimonial merely to make
   the copy more effective. A new campaign or sequence is a scope decision.
5. Use `japanese-writing` as expression knowledge, not a legacy workflow.
   `humanizer` is explicit-only and cannot change protected meaning. Style
   examples do not supply the client's results, customer stories or evidence.
6. Compare the full revision with the original and re-read it in context.
   Distinguish actual copy fields from production/QA notes. Check links,
   numbers, conditions and placeholders without claiming to have tested a live
   flow or rendered the destination. Unresolved required checks stay explicit.
7. Apply QA and deliver the complete revision at the requested path. Do not
   overwrite the source without authorization or patch a live page/email.
   A changed approved draft needs renewed approval; editing grants no right
   to publish, send, alter prices, run an experiment or change campaign records.

</Procedure>

<QA>

- Each change maps to the request; protected and untouched fields remain intact.
  Tone and length edits do not strengthen certainty or alter commercial terms.
- Claims and conditions agree across headlines, body, action and disclosures.
  New facts are supported; unresolved contradictions cannot be hidden by a
  style improvement. Absence of proof is not itself proof that a claim is false.
- No fabricated scarcity, urgency, endorsements or results. Existing numbers
  and evidence boundaries are not changed into broader guarantees.
- Render fit, legal compliance, delivery, endpoint behavior and conversion lift
  remain unverified without appropriate evidence. Hard limits need reliable
  counting with a method; required unmet/unverified checks are not complete.
- Report checked / unmet / unverified evidence. The complete draft remains
  usable without inserting field labels or QA notes into recipient-facing text.
  No legacy four-pass floor, automatic humanizer or naturalness score applies.

</QA>

<Report>

Name `edit-copy`, destination, original/revised paths and changed fields. Report
applicable criterion evidence, sources and unresolved conditions with only
necessary quotations. Deliver the complete revised file, not a fragment or an
unrequested live change. Corrections return to Writer; publication needs its own
approval and consumers do not rewrite the accepted part.

</Report>
