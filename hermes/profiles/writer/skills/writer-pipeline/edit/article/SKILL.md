---
name: edit-article
description: >-
  Edit an existing article within a stated wording, structure or rewrite
  scope, preserving its claims, quotations and media requirements. Adapt
  source notation to the destination without claiming editor or publish work.
  Not creating a new campaign, editing a live page or analyzing without edits.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised article and any updated same-stem .production.md; changed scope and unresolved finishing reported"
    form:
      source: {required: true, type: text, label: "Existing article text, local path or readable URL"}
      changes: {required: true, label: "Requested changes and affected sections"}
      scope: {required: false, options: [wording,structure,rewrite], label: "Default wording; broader changes require explicit authorization"}
      platform:
        required: false
        options: [x-article,note,zenn,blog]
        other: true
        references: references/*.md
        label: "Keep the original destination unless a change is requested"
      approved_outline: {required: false, type: text, label: "Approved outline/version; a path alone is not approval"}
      production_notes: {required: false, type: text, label: "Existing asset/editor notes or their path; required when unresolved markers need interpretation"}
      assets: {required: false, label: "Supplied replacement assets and approved descriptions, not permission to generate"}
      sources: {required: false, label: "Evidence for factual corrections or additions"}
      language: {required: false, label: "Keep the original language unless specified"}
      tone: {required: false, label: "Keep the original voice unless a change is requested"}
      style_reference: {required: false, label: "Expression/structure example, not a source of client experience"}
      reference_focus: {required: false, label: "What to adopt from the example"}
      length: {required: false, label: "Requested target or hard bound and units"}
      must_keep: {required: false, label: "Protected claims, caveats, quotations, code, links and asset IDs"}
      avoid: {required: false, label: "Requested exclusions; ask if they conflict with protected content"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other editing or platform constraints"}
---

<Procedure>

1. Read the complete source, change request and any approved outline or
   production notes. A missing target is a question, not permission to
   reconstruct an imaginary original. Identify protected meaning and the
   authorized edit scope. Wording edits do not reopen an approved structure.
2. Read the matching destination guidance only: [X Article](references/x-article.md),
   [note](references/note.md), [Zenn](references/zenn.md) or [blog](references/blog.md).
   An unknown/custom destination retains the supplied constraints; do not
   guess its markup support or silently convert the article to a post.
3. Edit only what the request authorizes. Keep source-backed claims,
   quotations, uncertainty and the author's actual experience. New claims
   need sources; a style example is not evidence. Use `japanese-writing`
   for Japanese expression, not the retired workflows or lint.
   Natural compounds and repeated formats are not errors by themselves.
   `humanizer` is explicit-only and cannot override protected meaning.
4. If the article has media/editor requirements, read
   [production notes](references/production/assets.md). Preserve stable IDs
   in `[[image:id]]`, `[[embed:id]]` and `[[table:id]]`
   and their source/placement requirements. Do not invent URLs, discard an
   unresolved marker, or claim missing media is now available. If a placement
   changes, update the corresponding note and report the mapping. Missing
   notes needed to interpret a marker are a blocker for that change.
5. Compare changes with the original, then re-read the article in context.
   Check section references, code/text boundaries and whether the title still
   matches the body. A substantial new purpose or stance needs a new decision,
   not a broad rewrite disguised as polishing.
6. Apply QA and save the complete revised article at the requested path.
   Save changed production notes beside it as `<draft-stem>.production.md`.
   Never overwrite the source without authorization or edit a live page.
   Previously approved text needs renewed approval after modification.

</Procedure>

<QA>

- Map edits to the request; untouched sections and protected wording remain
  unchanged unless broader changes were explicitly released.
- Claims, source attributions, negation, conditions and chronology survive
  shortening or reordered explanations. No invented personal experience.
- Used syntax matches known destination capabilities; rich-text editor work
  and a successful source edit are distinct. Current rendering and hard
  limits remain unverified without actual supporting evidence.
- Marker IDs and production-note records still agree. Required assets or
  editor actions remain needs-assets / needs-editor until completed by the
  responsible producer; the text edit does not complete them.
- Report applicable criteria as checked / unmet / unverified with evidence.
  This is self-review, not the requester's acceptance or publication approval.

</QA>

<Report>

Name `edit-article`, original/revised paths, changed sections and any asset-ID
or note changes. Report criterion evidence, sources and unresolved finishing.
Deliver the complete revised file, not a whole draft pasted in the reply.
Do not imply a live edit, successful preview, media creation or publication.

</Report>
