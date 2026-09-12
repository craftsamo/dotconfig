---
name: write-script
description: >-
  Write narration, a comic script, storyboard, screenplay or slide script from
  a released brief and the producer's text contract. Separate exact spoken or
  displayed words from instructions. Not executable code, audio/video/image
  generation, finished subtitles, voice selection or publication.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: writing
    output: "Complete script at the requested path, exact verbatim fields or spoken-text file, and necessary production notes; no rendered or synthesized media"
    form:
      audience: {required: true, label: "End reader/viewer/listener and relevant prior knowledge"}
      purpose: {required: true, label: "What the piece should convey or enact; no compulsory hook or CTA"}
      format:
        required: true
        options: [narration, comic, storyboard, screenplay, slide-script]
        other: true
        references: references/*.md
        label: "Infer the requested production format; a described custom format is equally valid"
      producer_format: {required: false, type: text, label: "Actual consumer, required fields, units and file representation; clarify missing requirements that determine usability"}
      source_story: {required: false, type: text, label: "Approved story, outline, scene inputs or existing material; identify fiction versus factual narration"}
      speakers: {required: false, type: text, label: "Known speaker identities and writing voices; not a voice-engine grant or invented registered voice ID"}
      duration: {required: false, label: "Requested duration or timing range, target versus hard requirement, and any existing timing evidence"}
      unit_limits: {required: false, type: text, label: "Released page/panel/scene counts or per-unit text limits with units; not universal defaults"}
      sources: {required: false, type: text, label: "Supporting facts, quotations, files/URLs or excerpts for factual content"}
      language: {required: false, label: "Explicit output preference wins; otherwise default Japanese"}
      tone: {required: false, label: "Writing voice in ordinary words; speaker-specific where relevant, not model or TTS controls"}
      style_reference: {required: false, type: text, label: "Expression or structure example, not this client's facts or characters"}
      reference_focus: {required: false, label: "Which aspects of the example to borrow"}
      must_keep: {required: false, label: "Protected words, speaker identities, order, facts or approved story constraints"}
      avoid: {required: false, label: "Excluded content; clarify conflicts with protected meaning or producer requirements"}
      length: {required: false, label: "Overall text target or hard bound with units; distinguish it from playback duration"}
      humanizer: {required: false, options: ["yes", "no"], label: "Default no; explicit request only"}
      note: {required: false, type: text, label: "Other requirements or custom producer constraints"}
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

1. Read the released brief and supplied story/evidence. Identify the intended
   audience and actual producer contract without asking for information already
   supplied. Clarify unresolved fields that affect consumption; a script's name
   alone does not prove an existing audio/video tool can execute it. Fictional
   invention belongs only inside the agreed story freedom, not factual narration,
   quotes, testimonials or real people's experiences.
2. Read only the selected format: [narration](references/narration.md),
   [comic](references/comic.md), [storyboard](references/storyboard.md),
   [screenplay](references/screenplay.md) or [slide script](references/slide-script.md).
   A custom format follows its supplied contract, not an assumed renderer.
   Written slide structure alone belongs to Document; a production script adds
   the requested spoken/displayed text and production roles.
3. Honor outline/piece/whole scope. An outline unit stops at the agreed structure
   and requested samples; a piece keeps approved scope and speaker decisions.
   A small plain narration needs no forced scene table or approval ceremony.
   A multi-part work beyond the released unit returns for decomposition.
4. For structured scripts, assign stable unique unit IDs and explicit order;
   use the producer's required fields and known speaker roster. Mark spoken and
   displayed text separately from action, camera, pronunciation and delivery
   notes. Do not add an unrequested hook, CTA, cast or fixed beats-per-second
   formula. Cross-unit references must identify the intended unit unambiguously.
5. Draft within the approved story and factual limits. Use `japanese-writing`
   as Japanese expression knowledge only, not legacy layers or inspection.
   `humanizer` is explicit-only and cannot change protected lines, speaker voice
   or source meaning. Keep linguistic voice separate from sound-engine selection.
6. Check textual limits by a reliable method and state that method. A rough
   reading-time estimate is not measured playback or synchronized subtitles.
   A hard production constraint without adequate evidence remains unverified;
   return the dependency rather than guaranteeing fit or silently dropping words.
   Use a supplied consumer's actual bounds, not a universal limit for all scripts.
7. Apply QA and save the complete artifact at the requested durable path. For
   a plain spoken-text consumer, the input file contains only intended words:
   no heading, speaker label, Markdown fence, stage direction or QA receipt.
   Put needed instructions in a separate same-stem `.production.md`. For a
   structured master, keep verbatim fields distinct; if raw per-unit files are
   required, deliver them at agreed paths and map unit/speaker to each file in
   the production notes, checking equality with the master. Never infer consent
   to synthesize, render or publish from a completed writing draft.

</Procedure>

<QA>

- The released unit and producer representation match the request; required
  fields/order and speaker identities are coherent. Plain narration has no
  unnecessary scene fields. Structured unit IDs are unique and addressable.
- Verbatim words are separable from every instruction. Raw spoken files contain
  only intended text; any companion notes/exports agree with the master and
  are not passed as speech input. No HTML-comment hiding assumption.
- Facts, quotes, conditions and approved story constraints survive. Fictional
  freedom is not evidence of real events. Speaker voice does not create a
  registered engine identity or performed voice-likeness claim.
- Counts cite a method; playback, lip/beat synchronization, pronunciation,
  rendered lettering, acting and production feasibility remain unverified
  without the corresponding evidence. A textual timing target is not a result.
- Use checked / unmet / unverified criterion evidence, not legacy passes or
  naturalness scores. Required unmet/unverified criteria are not complete.
  Writing self-review is neither independent acceptance nor production approval.

</QA>

<Report>

Name `write-script`, format, released unit, master/raw-text paths and any
production notes. Identify exact consumer inputs and applicable criterion
evidence, sources and open requirements. Deliver complete files, not the whole
draft pasted in the reply. An outline is not a final script; an accepted text
is not rendered/synthesized media or permission to start the consumer.

</Report>
