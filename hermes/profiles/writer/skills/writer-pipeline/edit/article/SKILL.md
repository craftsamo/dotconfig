---
name: edit-article
description: >-
  Edit an existing article within a stated proofread, wording, structure or
  rewrite scope, preserving its claims, quotations and media requirements.
  Proofreading corrects minimal, unambiguous errors without restyling. Adapt
  source notation to the destination without claiming editor or publish work.
  Not creating a new campaign, editing a live page or analyzing without edits.
version: 1.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised article and any updated same-stem .production.md; changed scope and unresolved finishing reported"
    form:
      source: {required: true, type: text, label: "Existing article text, local path or readable URL"}
      changes: {required: true, label: "Requested changes and affected sections"}
      scope: {required: false, options: [proofread,wording,structure,rewrite], label: "Default wording; proofread only when proofreading is actually requested; broader changes require explicit authorization"}
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
   reconstruct an imaginary original. Select the edit scope from the request:
   proofreading, typo-only or similar names `proofread`; polishing wording
   without changing structure is `wording` (the default); reorganizing
   sections is `structure`; a broad rewrite is `rewrite`. An explicit `scope`
   that conflicts with the request text (for example `scope: wording` beside
   "just fix the typos") is a `Q<n>:` question, not a silent pick. A
   findings-only request ("what's wrong with this") selects
   `analyze-article`; do not execute edits for it. Identify protected meaning
   and the authorized edit scope. Wording edits do not reopen an approved
   structure. A bounded proofreading or wording pass on an existing article
   needs no new outline, tone or reader research.
2. For `proofread` scope, limit changes to minimal, clearly identifiable
   errors: typos, duplicated or missing characters, unambiguous grammar,
   punctuation or bracket-matching mistakes, and inconsistencies against an
   agreed house notation. Preserve the author's voice, meaning, order and
   intentional stylistic variation; `japanese-writing` supplies house
   notation knowledge, not permission to restyle the original. Quotations,
   code, URLs, identifiers, asset markers and any `must_keep` content stay
   unchanged absent explicit, item-specific authorization; a blanket
   normalization request is not such authorization. An unfamiliar proper noun,
   a suspicious number or a fact inconsistent with the rest of the source is
   flagged, not silently corrected by inference.
3. Read the matching destination guidance only: [X Article](references/x-article.md),
   [note](references/note.md), [Zenn](references/zenn.md) or [blog](references/blog.md).
   An unknown/custom destination retains the supplied constraints; do not
   guess its markup support or silently convert the article to a post.
4. Edit only what the request authorizes. Keep source-backed claims,
   quotations, uncertainty and the author's actual experience. New claims
   need sources; a style example is not evidence. Use `japanese-writing`
   for Japanese expression, not the retired workflows or lint.
   Natural compounds and repeated formats are not errors by themselves.
   `humanizer` is explicit-only and cannot override protected meaning.
5. If the article has media/editor requirements, read
   [production notes](references/production/assets.md). Preserve stable IDs
   in `[[image:id]]`, `[[embed:id]]` and `[[table:id]]`
   and their source/placement requirements. Do not invent URLs, discard an
   unresolved marker, or claim missing media is now available. If a placement
   changes, update the corresponding note and report the mapping. Missing
   notes needed to interpret a marker are a blocker for that change. Inspect
   notes only to the extent the actual scope touches them: an unrelated
   marker with unavailable notes is reported, not a blocker for an unrelated
   typo fix, and notes are never fabricated or altered to manufacture
   resolution.
6. Compare changes with the original, then re-read the article in context.
   Check section references, code/text boundaries and whether the title still
   matches the body. A substantial new purpose or stance needs a new decision,
   not a broad rewrite disguised as polishing.
7. Apply QA and save the complete revised article at the requested path.
   Save changed production notes beside it as `<draft-stem>.production.md`.
   Never overwrite the source without authorization or edit a live page.
   Previously approved text needs renewed approval after modification.
   Finding no qualifying errors is a legitimate no-op: when a new output
   path was requested, deliver the complete unchanged text there, leave the
   original untouched, and report that no changes were made.

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
- A bounded proofread or wording pass does not add new fact-checking, source
  research or unrelated editor evidence as completion requirements. Explicitly
  requested factual checks still need evidence; a recorded uncertainty
  documents a limit and does not certify facts, rendering or publication.
- Confirmed corrections, uncertain issues and optional style suggestions stay
  in three distinct groups; do not fold an unsolicited style suggestion into
  an applied change.
- A no-op (no qualifying errors found within the authorized scope) is a valid
  outcome, not a failure to report; the delivered text and any new-path
  output remain identical to the source, and the report names the checked
  scope and the empty result.
- Report applicable criteria as checked / unmet / unverified with evidence.
  This is self-review, not the requester's acceptance or publication approval.

</QA>

<Report>

Name `edit-article`, original/revised paths, changed sections and any asset-ID
or note changes. Report criterion evidence, sources and unresolved finishing.
Deliver the complete revised file, not a whole draft pasted in the reply.
For `proofread` scope, include a short before/after and reason for corrections
in this reply report; group repeated corrections rather than duplicating the
whole article. This is not a new mandatory sidecar file.
Do not imply a live edit, successful preview, media creation or publication.

</Report>
