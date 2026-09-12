---
name: analyze-script
description: >-
  Describe, review or compare an existing narration, comic script, storyboard,
  screenplay or slide script using its words and producer contract. Return
  unit/field-anchored observations, not rewritten dialogue, rendered-media
  analysis, guessed timing, code review or production approval.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Script analysis with anchored observations, interpretation and production uncertainties; original and exports unchanged"
    form:
      source: {required: true, type: text, label: "Existing script text, local path or readable URL and relevant supplied companion files"}
      question: {required: true, label: "What to explain or check about the actual script"}
      mode: {required: false, options: [describe, review, compare], label: "Infer from the question; description need not identify defects"}
      focus: {required: false, type: text, label: "One or more aspects: structure, speaker voice, continuity, verbatim boundaries or producer constraints"}
      format:
        required: false
        options: [narration, comic, storyboard, screenplay, slide-script]
        other: true
        references: references/*.md
        label: "Infer the target's format; needed only for format-specific analysis"
      producer_format: {required: false, type: text, label: "Actual expected fields, unit IDs/order and file representation when assessing usability"}
      unit_limits: {required: false, type: text, label: "Known per-unit count/text constraints with units; not inferred from genre"}
      timing_evidence: {required: false, type: text, label: "Supplied timing evidence and the exact script version it covers, if relevant"}
      criteria: {required: false, label: "Known audience, purpose, speakers, story constraints or acceptance requirements"}
      compare_with: {required: false, type: text, label: "Comparison script/path/URL; required for compare"}
      sources: {required: false, type: text, label: "Evidence for factual observations; not permission to render, synthesize or research new facts"}
      language: {required: false, label: "Report language; default to the requester's language"}
      length: {required: false, label: "Requested analysis depth or report length"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit observations only, never permission to rewrite"}
      note: {required: false, type: text, label: "Other analysis questions or constraints"}
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

1. Read the actual script and question. A missing target returns to the requester;
   pre-draft story advice is consultation, not invented analysis. State the read
   scope and unavailable context. A bounded dialogue/structure question does
   not require a complete writing brief or a production contract it does not use.
2. Choose describe/review/compare; comparisons read both inputs. When format
   criteria matter, read only [narration](references/narration.md),
   [comic](references/comic.md), [storyboard](references/storyboard.md),
   [screenplay](references/screenplay.md) or [slide script](references/slide-script.md).
   Custom formats retain their supplied criteria, not assumed renderer support.
3. Anchor observations to unit IDs, speakers, fields or short quotations.
   Explain textual structure, attribution and continuity within the evidence.
   Separate what the script states, your interpretation and actual unknowns.
   Description need not invent faults, a winner, a CTA or an alternative ending.
4. In a producer-fit review, compare required IDs/order/fields and exact-text
   boundaries with the supplied contract. Read relevant raw exports/notes when
   checking their consistency; a missing export limits that conclusion. The
   existence of a media tool does not prove it accepts this script representation.
5. Distinguish textual counts or timing intentions from measured performance.
   Existing timing evidence applies only to the covered version and conditions.
   Do not infer audio duration, acting, voice likeness, pronunciation, rendered
   legibility or synchronization from a script alone. Do not create media or
   mutate timing files to resolve an unknown.
6. Use `japanese-writing` for Japanese expression observations without legacy
   layers or inspection scripts. `humanizer` is explicit-only and cannot turn
   analysis into rewritten dialogue. No authorship/naturalness score or claim
   that a real speaker said words merely because they appear in a fictional script.
7. Apply QA to the analysis report, not an imaginary replacement script. Return
   a permitted short report in the reply or save it at the requested durable
   path. Original scripts, IDs and exports remain unchanged. Production approval
   and the requester's independent acceptance are separate from this analysis.

</Procedure>

<QA>

- Findings answer the question within the actual read scope and identify the
  relevant words/units. Observations, interpretations and unknowns are distinct.
  Comparisons use both inputs; description does not need a defect list.
- Producer-fit claims use the actual contract and inspected representations.
  Unknown format, unavailable exports or mismatched timing versions are not
  declared compatible. A textual suggestion is not a working production route.
- No unperformed audio/video/rendering check is claimed. Counts need a method;
  estimated duration is not measured playback, synchronized subtitles or acting.
- This report needs no new scenes, dialogue, speaker roster, raw speech file
  or production-ready fields of its own. It must not replace or renumber its
  target. Use checked / unmet / unverified evidence, not legacy passes or scores.

</QA>

<Report>

Name `analyze-script`, target/version, read scope, mode and relevant format.
Return anchored observations and requested recommendations with evidence and
production limitations. An analysis report is not a script part for synthesis
or rendering. Do not claim a rewrite, timing update or production approval.

</Report>
