---
name: edit-document
description: >-
  Edit an existing technical or business document within an authorized wording,
  structure or rewrite scope. Preserve facts, decisions, commands and reference
  identities. Not writing a new document from an absent source, analyzing only,
  modifying a repository, running procedures or verifying production behavior.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised document at the requested path; changed sections, preserved constraints and unresolved evidence reported"
    form:
      source: {required: true, type: text, label: "Existing document text, local path or readable URL"}
      changes: {required: true, label: "Requested changes and affected content"}
      scope: {required: false, options: [wording, structure, rewrite], label: "Default wording; broader changes require explicit authorization"}
      format:
        required: false
        options: [readme, guide, reference, report, minutes, proposal, slides, release-notes, issue]
        other: true
        references: references/*.md
        label: "Infer from the source; retain its format unless conversion is requested"
      sections: {required: false, label: "Section names or stable IDs covered by this edit"}
      sources: {required: false, type: text, label: "Evidence for corrections or additions, not permission to investigate systems"}
      template: {required: false, type: text, label: "Applicable existing format/conventions or an explicitly requested new template"}
      destination: {required: false, label: "Source/renderer constraints; preserve unless a change is requested"}
      approved_outline: {required: false, type: text, label: "Approved outline/version when this is a piece unit"}
      language: {required: false, label: "Keep the original language unless specified"}
      tone: {required: false, label: "Keep the original register unless a change is requested"}
      style_reference: {required: false, type: text, label: "Expression/organization example, not a replacement factual source"}
      reference_focus: {required: false, label: "What to borrow from the example"}
      length: {required: false, label: "Target or hard bound and its units"}
      must_keep: {required: false, label: "Protected facts, qualifications, quotations, commands, IDs, links or sections"}
      avoid: {required: false, label: "Requested exclusions; clarify conflict with protected content"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other editing conditions or custom format requirements"}
---

<Procedure>

1. Read the complete source, change request and applicable brief/template.
   Identify the authorized sections, scope and protected meaning. A missing
   original is a blocker; do not reconstruct it from a description. Distinguish
   source documentation from instructions to act on a system.
2. Read only the matching edit guidance: [README](references/readme.md),
   [guide](references/guide.md), [reference](references/reference.md),
   [report](references/report.md), [minutes](references/minutes.md),
   [proposal](references/proposal.md), [slides](references/slides.md),
   [release notes](references/release-notes.md) or [issue](references/issue.md).
   A custom format follows its known constraints. Do not silently change the
   document type, audience or purpose to make the edit easier.
3. Apply only the requested changes. Wording edits preserve statements,
   negation, conditions, decisions and uncertainty. Reorganization needs the
   released structure scope; a rewrite still preserves protected meaning.
   New factual corrections require sources. Source conflicts or ambiguous
   references go back to the requester rather than being silently resolved.
4. Preserve quoted commands, code, values, identifiers and links unless their
   change is authorized and supported. Preserve stable section/item IDs; if an
   authorized move affects a cross-reference, update the known dependents and
   report the change. Do not imply that unseen inbound links were checked.
   Unknown owners/dates remain unknown, not assigned by the editor.
5. Use `japanese-writing` for Japanese expression without the retired
   composition/inspection workflow. Natural compounds and repeated lookup
   formats are not defects. `humanizer` is explicit-request only and cannot
   remove a qualifier, quotation or other protected content.
6. Compare changes with the original and re-read the complete revised text in
   context. Check changed dependencies and format-specific meaning. Do not
   execute examples, test production behavior or render a deck to resolve a
   textual gap; state what the requester/engineer still needs to verify.
7. Apply QA and save the complete revised document at the requested path.
   Never overwrite the source without authorization or edit a live/repository
   destination as a substitute for handing off the text. A previously approved
   document needs renewed approval after modification.

</Procedure>

<QA>

- Map changes to the request. Untouched sections and protected content stay
  unchanged unless broader changes were explicitly released.
- Facts, decisions, source attributions, conditions and uncertainty survive
  shortening or rearrangement. Missing from the record is not a newly made
  decision; an unexplained discrepancy is not permission to select a value.
- Check command/code boundaries, values, table definitions, step order and
  affected cross-references. Documentation edits do not establish execution
  success, production state or external-link validity.
- Preserve unresolved source, asset and renderer dependencies. Hard bounds
  without reliable measurements stay unverified, not silently satisfied.
- Use checked / unmet / unverified evidence for the actual edited artifact.
  This is self-review; no independent acceptance, legacy lint or automatic
  humanizer pass is implied.

</QA>

<Report>

Name `edit-document`, format, original/revised paths, affected sections and any
identifier/reference changes. Give applicable criterion evidence and unresolved
checks. Deliver the complete revision, not a fragment or a whole draft pasted
in the reply. Do not claim repository integration, execution or publication.

</Report>
