---
name: analyze-post
description: >-
  Explain, review or compare existing X posts/threads or Instagram captions
  against a requested question. Return anchored findings without rewriting
  or publishing. Not campaign planning, metric collection or AI-authorship scoring.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Evidence-anchored post analysis; observations, interpretations and unknowns separated; source unchanged"
    form:
      source: {required: true, type: text, label: "Existing post/thread/caption text, local path or readable URL"}
      question: {required: true, label: "What the requester wants to understand or verify"}
      platform:
        required: true
        options: [x, instagram]
        references: references/*.md
        label: "Platform of the source text"
      mode: {required: false, options: [describe,review,compare], label: "Infer from the question; no automatic defect hunt"}
      focus: {required: false, type: text, label: "One or more requested aspects: message, progression, tone, claims, media fit or action"}
      criteria: {required: false, label: "Known audience, intent and constraints for a requested review"}
      compare_with: {required: false, type: text, label: "Other text/path/URL; required when a comparison is requested"}
      context: {required: false, label: "Surrounding posts, reply context, audience or intended outcome"}
      format: {required: false, label: "Single post, thread or caption; infer from the supplied material"}
      media: {required: false, label: "Supplied media or descriptions and their source; unavailable visual evidence stays unknown"}
      sources: {required: false, label: "Evidence for claim checking, not an instruction to perform independent research"}
      language: {required: false, label: "Report language; default to the requester's language, not necessarily the source"}
      length: {required: false, label: "Requested report length or depth"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit use supplies analysis guidance only, never permission to rewrite"}
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

1. Read the actual source and question. If there is no existing text,
   return a planning-consultation request to the pipeline rather than
   analyzing an invented post. Retrieve only supplied sources with the
   available tools; inaccessible content is not evidence of what it says.
2. Read only [X](references/x.md) or [Instagram](references/instagram.md).
   Infer describe/review/compare from the question; ask if the intended
   outcome changes the analysis. For compare, obtain both texts and use
   common criteria. A style description does not require a list of defects.
3. Anchor observations in exact wording, post IDs and the visible order.
   Review against supplied goals, not generic marketing templates. Mark
   interpretations as interpretations; tone does not prove how an audience
   reacted. Distinguish inspected media from a caller's description.
4. For Japanese language observations, use `japanese-writing` as knowledge,
   not its legacy inspection workflow, lint or scores. Use `humanizer` only
   on explicit request and only as guidance for findings. Do not diagnose
   authorship or turn statistical regularity into a naturalness verdict.
5. Check the report under QA below. Return the analysis, not revised post
   bodies. A small illustrative suggestion may explain a finding, but a
   corrected draft requires a separately requested edit. Never change the
   source, collect live metrics, run a test post or publish anything.

</Procedure>

<QA>

- Does the report answer the requested question and cover the material it
  claims to have read? Cite the source/post ID for each substantive finding.
- Descriptions identify features without inventing defects; comparisons
  use both sources and comparable conditions, not a predetermined winner.
- Separate wording/structure observations, interpretation and missing
  evidence. Text alone cannot establish visual quality, conversion effects,
  audience sentiment, live engagement or an account's platform capabilities.
- A supplied fact can be checked for faithful representation; independent
  truth remains unverified without supporting research evidence.
- The source is unchanged. Evaluate this analysis as a report, not as a
  new post requiring attachments, hashtags or a call to action.
- Report unmet or unverified requested checks rather than filling gaps
  with a score. A short response is valid when it answers the question.

</QA>

<Report>

Name `analyze-post`, the source and scope, then give anchored observations
and any requested recommendations. For review, name applicable criteria
and checked / unmet / unverified evidence. Keep unknowns explicit. A short
analysis may be returned in the reply; a requested durable report goes to
the named path. No corrected post or publication is implied.

</Report>
