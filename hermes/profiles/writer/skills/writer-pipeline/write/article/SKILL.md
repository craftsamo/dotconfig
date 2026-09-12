---
name: write-article
description: >-
  Write an explanatory article, tutorial, experience report or comparison
  for Zenn, note, X Articles or a blog. Respect platform authoring formats
  and distinguish text drafts from media/editor finishing. Not social posts,
  reference documentation, production scripts, marketing strategy or publishing.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Article or released outline at the requested path; optional same-stem .production.md with unresolved assets/editor work"
    form:
      topic: {required: true, label: "The subject and scope of the article"}
      reader: {required: true, label: "The intended reader and relevant prior knowledge"}
      purpose: {required: true, label: "What the reader should understand or be able to do"}
      platform:
        required: false
        options: [x-article, note, zenn, blog]
        other: true
        references: references/*.md
        label: "Destination; unspecified means a portable source draft, not verified platform fit"
      approach:
        required: false
        options: [explanation, tutorial, experience, comparison]
        other: true
        references: references/approach/*.md
        label: "Choose from the brief; a described approach is equally valid"
      sources: {required: false, label: "Source paths, URLs or excerpts; required for specific results, quotations and personal experiences"}
      language: {required: false, label: "Output language; default Japanese unless specified"}
      tone: {required: false, label: "Desired voice in ordinary words, not model temperature"}
      style_reference: {required: false, label: "Example article for expression or structure, not client facts"}
      reference_focus: {required: false, label: "What to borrow from the example and what not to borrow"}
      length: {required: false, label: "Target or hard bound with units; no universal platform limit is assumed"}
      approved_outline: {required: false, type: text, label: "Approved outline/version for a piece unit; a path alone is not approval"}
      assets: {required: false, label: "Asset IDs, kinds, supplied paths/URLs, known descriptions and intended placement"}
      asset_policy: {required: false, options: [supplied-only,plan-missing], label: "Default supplied-only; plan-missing allows explicit insertion requirements, not asset generation"}
      must_keep: {required: false, label: "Exact claims, quotations, terms, links or other protected content"}
      avoid: {required: false, label: "Excluded content or expressions; resolve conflicts before drafting"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other requirements, including custom platform constraints"}
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

1. Read the released brief and materials. Infer answered fields; ask Q<n>
   only where missing information changes the article. Decide the question
   or purpose the article serves without inventing the client's position,
   experience or results. A factual gap is not filled by fluent prose.
2. Read only the selected destination: [X Article](references/x-article.md),
   [note](references/note.md), [Zenn](references/zenn.md) or
   [blog](references/blog.md). For an unspecified/custom destination, retain
   its stated constraints and use a portable source draft for the rest;
   do not silently coerce it into a known platform or promise rendering.
   Read only the selected approach: [explanation](references/approach/explanation.md),
   [tutorial](references/approach/tutorial.md), [experience](references/approach/experience.md)
   or [comparison](references/approach/comparison.md).
3. Honor the released unit. An outline unit returns structure and requested
   tone samples, then stops for approval. A piece follows the approved
   outline and voice. A small whole job need not invent a separate approval
   round. Do not draft an entire series when only one article was released.
4. Write the article so the title/opening promise is supported by the body.
   Choose the explanation order for the actual topic; do not require every
   article to start with a conclusion or end with a CTA. Distinguish source
   facts, interpretation and unknowns. Tutorials use supplied/verified
   behavior; writing code snippets does not prove they were executed.
5. Use `japanese-writing` for Japanese expression and its notation defaults.
   It is not a composition or inspection workflow. Do not load the legacy
   prose/rhythm/business layers or run their lint. Preserve meaning and
   natural expressions; use `humanizer` only on explicit request.
6. If assets or editor-only features are needed, read
   [production notes](references/production/assets.md). Keep supplied media, source
   evidence and style examples distinct. Missing assets under supplied-only
   require a decision; plan-missing permits an explicitly incomplete draft
   with insertion requirements. Never generate, capture or upload media.
7. Apply QA, save the complete released artifact and report it. For rich-text
   destinations, distinguish the readable source draft from required editor
   operations. Do not claim a Markdown source file was imported, previewed
   or published. Approval and assembly stay with the requester/producer.

</Procedure>

<QA>

- Check the released unit, purpose, title promise and explanation against
  the supplied sources. Do not judge an outline as a completed manuscript.
- Quotations, numerical claims, examples and personal experiences retain
  their actual evidential status. A sample execution is not a verified run.
  Adjacent facts do not establish an action/result guarantee: do not add
  "even after changing X" or invent the comparison baseline of "unchanged".
- Preserve required content, qualifiers and the selected voice. A style
  example cannot supply facts or justify changing the client's stance.
- Compare used syntax with the destination's capability notes. Unsupported
  or unverified formatting needs a named alternative or editor step; not
  a claim of successful rendering. Hard limits need an actual reliable
  measurement and method, otherwise remain unverified.
- Every insertion marker resolves to a uniquely identified production note.
  Missing assets, unfinished embeds or required editor work remain visible
  dependencies. Text completion is not publication readiness. Never hide
  notes in HTML comments or silently discard unresolved requirements.

</QA>

<Report>

Name `write-article`, destination, approach, released unit and artifact path.
If present, name the same-stem production-notes path and unresolved IDs.
For applicable criteria report checked / unmet / unverified with quotes,
sources or measured values and methods. State text complete, needs-assets,
needs-editor or the actual blocker as appropriate; these are artifact states,
not independent acceptance. Do not paste a whole draft in the reply or
claim a publication, working embed, live preview or asset-generation result.

</Report>
