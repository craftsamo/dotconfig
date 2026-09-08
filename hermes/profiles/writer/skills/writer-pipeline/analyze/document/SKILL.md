---
name: analyze-document
description: >-
  Describe, review or compare existing technical and business documents using
  quoted evidence and known format criteria. Distinguish missing records from
  decisions and text quality from runtime validity. Return analysis without
  rewriting, executing procedures, researching facts or producing a new document.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Evidence-anchored document analysis with scope and unknowns; source unchanged"
    form:
      source: {required: true, type: text, label: "Existing document text, local path or readable URL"}
      question: {required: true, label: "What should be explained or checked"}
      mode: {required: false, options: [describe, review, compare], label: "Infer from the question; a description need not find defects"}
      focus: {required: false, type: text, label: "One or more aspects: coverage, lookup, task order, consistency, evidence, ambiguity or wording"}
      format:
        required: false
        options: [readme, guide, reference, report, minutes, proposal, slides, release-notes, issue]
        other: true
        references: references/*.md
        label: "Infer from the target; needed only for format-specific judgments"
      criteria: {required: false, type: text, label: "Known reader, purpose, scope and acceptance conditions"}
      compare_with: {required: false, type: text, label: "Other document text/path/URL; required for compare"}
      sources: {required: false, type: text, label: "Supplied evidence for factual checks; no independent research implied"}
      template: {required: false, type: text, label: "Required document convention when compliance is in scope"}
      destination: {required: false, label: "Known renderer or destination constraints; not proof of actual rendering"}
      language: {required: false, label: "Report language; default to the requester's language"}
      length: {required: false, label: "Requested analysis depth or report length"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit analysis guidance only, never permission to rewrite"}
      note: {required: false, type: text, label: "Other analysis requirements"}
---

<Procedure>

1. Read the target and the question. State the scope actually available; a
   truncated document cannot support whole-document conclusions. An absent
   target goes back to the requester. Advice before a document exists is a
   planning consultation, not an analysis of an imaginary text.
2. Infer describe/review/compare from the question. A comparison reads both
   inputs and uses common criteria, accounting for different versions, periods
   or audiences. Ask only for criteria necessary for the requested judgment;
   a wording question does not require a full new-document brief.
3. For format-specific analysis, read only [README](references/readme.md),
   [guide](references/guide.md), [reference](references/reference.md),
   [report](references/report.md), [minutes](references/minutes.md),
   [proposal](references/proposal.md), [slides](references/slides.md),
   [release notes](references/release-notes.md) or [issue](references/issue.md).
   Judge custom formats against their supplied constraints, not a nearby type.
4. Anchor observations to passages, section names, row labels or stable IDs.
   Separate observed omissions/inconsistencies from possible reader effects
   and recommended changes. Describe a format without manufacturing defects.
   A missing record does not prove an event or decision never happened.
5. Check factual assertions only to the extent supported by supplied evidence.
   Do not execute commands, follow a runbook, reproduce bugs, inspect systems
   or certify a rendered presentation. An apparent valid command is not a
   successful test. Missing evidence is unverified, not proof of falsehood.
6. Use `japanese-writing` for Japanese-language observations, not retained
   legacy workflows or statistical scoring. `humanizer` is explicit-only;
   even when used, it supplies analysis rather than a replacement document.
7. Apply QA to the report, not to an imaginary newly written source document.
   Return a permitted short report in full in the reply, or save a longer
   report at the requested durable path. Keep original files unchanged.

</Procedure>

<QA>

- The report answers the actual question and distinguishes observations,
  interpretations and unknowns. Its substantive findings identify evidence.
- A comparison uses both texts; a description does not require a defect list.
  Missing or conflicting source material limits conclusions instead of
  prompting invented owners, results, decisions or recommendations.
- Source format requirements apply to the target only when in scope. The
  analysis report need not contain a new README quick start, meeting attendees,
  owners, deadlines, slide content or a new report's research method.
- Text inspection is distinct from execution, rendered layout and real-system
  verification. Do not invent measurements, naturalness scores or authorship
  verdicts. Preserve the limits of any unperformed check.
- The original is unchanged. An illustrative explanation is not permission
  to provide a corrected full document, commit files or publish anything.

</QA>

<Report>

Name `analyze-document`, target, read scope and requested mode. Give anchored
observations and requested recommendations with checked / unmet / unverified
evidence. Identify missing comparison, source or runtime evidence. This is an
analysis report, not a new document, independent fact verification or repair.

</Report>
