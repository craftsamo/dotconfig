---
name: edit-script
description: >-
  Edit an existing narration, comic script, storyboard, screenplay or slide
  script within authorized units and fields. Preserve stable IDs, speakers,
  protected words and the producer contract. Not audio/video editing, code
  changes, automatic retiming, production or analysis-only requests.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete revised script and required exact-text exports/production notes, changed-unit evidence and pending production checks"
    form:
      source: {required: true, type: text, label: "Original script text, local path or readable URL; include relevant companion notes/exports"}
      changes: {required: true, label: "Requested changes to words, units, story or producer fields"}
      scope: {required: false, options: [wording, structure, rewrite], label: "Default wording; broader changes require explicit authorization"}
      format:
        required: false
        options: [narration, comic, storyboard, screenplay, slide-script]
        other: true
        references: references/*.md
        label: "Infer the original format; keep it unless a change is requested"
      target_units: {required: false, type: text, label: "Units/fields to change; preserve everything not named"}
      producer_format: {required: false, type: text, label: "Consumer's actual field/ID/file contract, including any approved format changes"}
      speakers: {required: false, type: text, label: "Known speaker roster and explicitly requested voice/identity changes"}
      duration: {required: false, label: "Requested timing target or hard bound and existing evidence; editing text is not retiming media"}
      unit_limits: {required: false, type: text, label: "Actual requested counts or per-unit limits with units"}
      sources: {required: false, type: text, label: "Evidence for factual corrections and additions"}
      language: {required: false, label: "Keep the source language unless specified"}
      tone: {required: false, label: "Keep each speaker's voice unless its change is requested"}
      style_reference: {required: false, type: text, label: "Expression example, not new facts, characters or producer requirements"}
      reference_focus: {required: false, label: "What to borrow from the example"}
      must_keep: {required: false, label: "Protected wording, unit IDs/order, speaker identities, facts or continuity constraints"}
      avoid: {required: false, label: "Requested exclusions; clarify conflicts with protected content"}
      length: {required: false, label: "Target or hard text bound with units, separate from playback duration"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other edit constraints, including required raw-text export paths"}
---

<Procedure>

1. Read the complete original, required companion files, changes and release
   constraints. Identify editable units/fields and protected words, IDs and
   speaker decisions. A missing original is a question, not permission to
   create one. Broader story or format changes need explicit authorization.
2. Read only the matching edit guidance: [narration](references/narration.md),
   [comic](references/comic.md), [storyboard](references/storyboard.md),
   [screenplay](references/screenplay.md) or [slide script](references/slide-script.md).
   Preserve a custom producer contract instead of coercing it into a listed one.
3. Apply the named changes. Existing unit IDs are stable: mark removed units
   as retired in the structure/production notes, never speak that marker or
   compact/reuse the IDs. Add new IDs without collisions. If re-identification
   is genuinely requested, obtain an explicit old-to-new mapping accepted by
   the requester and consumer before changing IDs or dependent references.
4. Preserve untouched fields, quotations, factual uncertainty and each speaker's
   identity/voice. Re-read neighboring units for changed references, entrances,
   knowledge or continuity. A shorter line must not change a possibility into
   a promise or remove a required condition. New factual assertions need evidence;
   an authorized fictional change must still fit the agreed story constraints.
5. Use `japanese-writing` as expression knowledge, not legacy inspection.
   `humanizer` is explicit-only and cannot override protected text or continuity.
   Wording changes are not authorization to select a voice engine, synthesize
   speech, edit footage or retime an existing subtitle/media file.
6. Compare the full revision with the original, including untouched units and
   requested exports. Keep exact spoken/displayed text separate from instructions.
   Update required raw-text exports and their unit/speaker mappings consistently;
   no stale export may be delivered as the revised approved words. Plain speech
   input remains words only, with notes in a separate `.production.md` file.
7. Apply QA and deliver the complete revision to the requested path without
   overwriting the source unless authorized. A changed approved script needs
   renewed approval, and dependent renders, audio and timing evidence are not
   automatically valid for the new words. Report what needs re-verification;
   do not start production or silently split it into additional jobs/takes.

</Procedure>

<QA>

- Changes match the authorized scope; untouched and protected fields remain
  intact. IDs and references are stable, removed IDs are not reused, and any
  approved remapping is explicit. Retired-unit notes are never verbatim lines.
- Speaker attribution, cross-unit continuity, quotes, conditions and uncertainty
  survive. Style/length edits do not change factual meaning or story decisions.
- Master, raw spoken files and production notes agree where exports are required.
  No headings, labels, fences or instructions leak into the spoken payload.
- Text counts have a reliable method. Reusing old duration or rendering evidence
  after changing words is not verification of the revision. Unmet or unverified
  required production constraints remain open, not a manufactured completion.
- Report checked / unmet / unverified evidence; no legacy four-pass floor,
  automatic humanizer or statistical score. Editing is not production approval.

</QA>

<Report>

Name `edit-script`, format, original/revised paths, changed units/fields and
any required raw exports/production notes. Give applicable evidence, protected
content checks and invalidated downstream assumptions. The consumer receives
the complete revision after acceptance; no audio, video, rendering or timing
was updated by this text edit, and no approved part is silently replaced.

</Report>
