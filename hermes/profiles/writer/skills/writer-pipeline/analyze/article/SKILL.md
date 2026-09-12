---
name: analyze-article
description: >-
  Describe, review or compare existing articles, their reasoning, voice,
  notation and destination representation, including a proofreading-focused
  review that reports likely errors without correcting them. Return
  source-anchored analysis without rewriting or publishing. Not pre-draft
  consultation, factual research, live analytics or AI-authorship scoring.
version: 1.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Analysis report with quoted evidence, interpretations and unknowns; original article unchanged"
    form:
      source: {required: true, type: text, label: "Existing article text, local path or readable URL"}
      question: {required: true, label: "What the requester wants explained or checked"}
      mode: {required: false, options: [describe,review,compare], label: "Infer from the question; description need not find defects"}
      focus: {required: false, type: text, label: "One or more aspects: proofreading, reasoning, evidence, structure, voice, audience fit or markup"}
      platform:
        required: false
        options: [x-article,note,zenn,blog]
        other: true
        references: references/*.md
        label: "Source or intended destination; required only when assessing platform fit"
      criteria: {required: false, label: "Known purpose, reader, constraints and acceptance criteria"}
      compare_with: {required: false, type: text, label: "Comparison text/path/URL; required for compare"}
      sources: {required: false, label: "Supplied evidence for factual checks; no independent research implied"}
      assets: {required: false, label: "Actual media or attributed descriptions, with IDs and provenance"}
      production_notes: {required: false, type: text, label: "Existing insertion/editor requirements and their unresolved states"}
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

1. Read the source and the actual question. A missing article goes back to
   the requester; future-article advice is a consultation, not a fabricated
   analysis. Inspect the available scope and state any incomplete source.
2. Select describe/review/compare from the request. Read both texts for a
   comparison and use common criteria. For platform-specific assessment,
   read only [X Article](references/x-article.md), [note](references/note.md),
   [Zenn](references/zenn.md) or [blog](references/blog.md). Unknown/custom
   destination behavior is not inferred from a familiar platform.
3. Anchor substantive observations to quoted passages or section locations.
   Distinguish the argument's structure, evidence and stated uncertainty.
   Describe voice without inventing author identity, experience or intent.
   If asked only for a description, do not manufacture defects or rankings.
4. When the question or `focus` requests proofreading (typos, grammar,
   punctuation, notation consistency), report each finding with its quote or
   location, the reason it is flagged and a suggested correction where warranted.
   Distinguish a definite error from an uncertain issue or an optional style
   suggestion; do not merge them into one list. This report never edits the source and
   delivers no replacement article; a match verified only against supplied
   material is reported as checked against that material, not as
   independently verified fact, and no finding is fabricated to fill out
   the requested depth.
5. When asset/editor requirements are in scope, read
   [production notes](references/production/assets.md). Inspect them only
   to the requested extent. An
   unresolved insertion marker shows planned content, not an image that can
   be analyzed. A source file does not prove successful rendering or working
   embeds. Attribute supplied descriptions and report unavailable evidence.
6. Use `japanese-writing` for Japanese-language observations without loading
   legacy workflows or statistical detectors. `humanizer` is explicit-only
   and supplies observations, never a rewritten article or authorship score.
7. Apply QA to the analysis report. Return it in the reply if short and
   permitted, or at the requested durable path. Do not alter the source,
   publish, access live analytics or execute code from the article.

</Procedure>

<QA>

- The report answers the question within the read scope and names evidence
  for its substantive findings. Observations and interpretations are distinct.
- Descriptions do not require defects. Comparisons use both sources and
  state differences in audience, evidence or conditions that affect conclusions.
- A citation can be checked against supplied material without treating that
  material as independently verified truth. Unsupported factual conclusions
  or claimed personal experience remain unverified, not fabricated evidence.
- Markup intent, documented platform support and actual rendering are
  separate. An unseen image, untested embed or unspecified CMS cannot pass
  a visual/platform check by resemblance or a file extension.
- Original text and production notes are unchanged. QA evaluates this report,
  not a new article that would need its own introduction, CTA or media assets.
  No naturalness score, author detector or fake runtime measurement is used.

</QA>

<Report>

Name `analyze-article`, source, scope and requested mode. Provide anchored
observations and requested recommendations, with applicable checks marked
checked / unmet / unverified. Preserve missing-source and rendering limits.
Do not deliver a replacement article, pretend to have inspected absent media,
or convert a qualitative reading into a numeric quality/authorship verdict.

</Report>
