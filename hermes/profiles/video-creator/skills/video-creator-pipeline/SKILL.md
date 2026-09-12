---
name: video-creator-pipeline
description: >-
  Root of video-creator's clip, MV, authored-UI-tour, ad and authored-explainer-video leaves. Load first for a filled form naming
  generate-clip, edit-clip, analyze-clip, generate-music-video, create-tour, create-ad, analyze-ad or create-explainer-video, then load only that leaf.
  Not an interview, a video menu, or a generic movie-making workflow.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [video, hands, pipeline]
    category: hands
---

<InstructionContext>

For execution as video-creator, re-evaluate the named leaf and its selected
references on every inbound turn or completion, and before an action changes
operation, subject or form options. Use the current request and retained approved
job together; a new selection is not permission to expand the released work.
Return an unreleased change to Creator rather than substituting a leaf or grant.
This execution contract does not turn Creator's inspection of a form into a
hands run. Clients read forms; only the owning hands executes the procedure.

Require the full kernel, selected leaf and required reference bodies in current
context before the affected action. Reuse those bodies, not a past load, summary
or preload marker. Load missing bodies with skill_view, using the named leaf's
file_path for its selected references. Read only applicable options, not the
whole reference tree. Optional advisory references retain their existing fallback.

If skill_view returns unchanged but the earlier body is unavailable, use
read_file on the canonical document: this kernel is
`${HERMES_SKILL_DIR}/SKILL.md`; a leaf is
`${HERMES_SKILL_DIR}/<verb>/<subject>/SKILL.md`, and its references resolve from
that leaf's directory. In raw file text, `${HERMES_SKILL_DIR}` always denotes the
document's owning skill root, not the last loaded skill. Follow next_offset for
a genuinely truncated read; never use alternate paths or artificial ranges to
evade deduplication. If required instructions remain unavailable, stop the
affected action and report the missing document.

Loading instructions never restarts production, restores spent attempts or
changes approval, engine, inputs or budget. Reuse surviving outputs and preserve
the existing proposal/preview and revision gates.

</InstructionContext>

<Run>

The runtime specialist header is agent context outside the form, not human
approval. Preserve the initial learning goal and selected performance/engine.
Use supported local authoring rather than fixed scene recipes; missing advice
does not remove a working renderer. Real missing inputs remain dependencies,
not permission to downgrade the performance or silently switch engines.
Act only on the current agent request. The retained initial form supplies
historical constraints, never a request to repeat its generation or spend.

1. Read `skill`, `intent`, `deliver`, optional `budget`, and `form`.
   Load the named leaf. Validate required fields, types, local paths and
   options (`other: true` accepts a described value). Return one batched
   `Q<n>:` for missing/unusable fields; unknown leaf: `no skill fits`.
   Analyze may omit `deliver`; its evidence stays in a fresh scratch dir.
   analyze-ad may retain its report/evidence at an explicit deliver path;
   it never produces a new ad. Use kind="work" for its bounded multi-pass review.
   A2A's loopback IP is normal transport metadata, not a missing form field;
   the transport does not authenticate a profile name. Never ask the caller
   to prove its role by saying "I am Creator".
2. Load only the leaf's selected references and previous delivery for
    `intent: revise`. Reuse surviving intermediates before any new spend.
   Before a creative decision or perceptual review, apply
   [craft reading](references/craft.md). Pure trim/re-encode/metadata work skips it.
3. Follow `<Procedure>`; no TTS, image generation, improvised pipelines, or
   outside workflows. The knowledge-only craft reading above is separate from
   create-tour/create-ad/create-explainer-video's own
   optional, read-only [HyperFrames references](references/hyperframes.md),
   consulted only when that leaf's own contract calls for it, never as a
   substitute leaf or workflow. create-explainer-video authors a bounded
   (1..180s) topic/audience/learning_goal explanation only, rendering
   through either v1 HyperFrames (HTML/UI or media-oriented compositions)
   or v2 Motion Canvas (reactive diagrams, algorithms, Canvas-based
   explanation) at 16:9/9:16 30fps — an explicit engine choice made and
   preserved in the proposal, never a silent switch on failure. Motion
   Canvas needs no external HyperFrames skills; it uses its own local
   motion-canvas reference inside that leaf. Old version 1 Motion Canvas
   discussion proposals stay non-executable and need a new version 2
   proposal and approval. Neither engine gives automatic phoneme/viseme
   inference or native talking-model playback. A missing required
   performance asset (character art, script,
   narration) is a dependency request back to Creator, reported as
   pending-inputs — never invented and never a silent downgrade of
   framing/performance/lip_sync. generate-music-video authors a proposal within its form;
   no approved proposal/digest means no generation, even with a budget.
   create-ad permits task-local HTML/CSS/GSAP advertising from supplied assets:
   content-plan approval, frozen-source preview, then exact-preview approval
   before final rendering. No approval fields means proposal only, not render.
   For create-ad/create-tour, `audio_workflow: mix` with no `mix_bundle`
   first returns a preliminary timing proposal through Creator, not a formal
   video approval. AudioCreator owns Mix design/rendering. With the finished
   bundle, stage its verified master/receipt/captions/timing before normal
   video approval. No placeholders, source-stem double playback, direct hands
   calls or new MV/clip finishing. Simple supplied audio stays unchanged.
   create-tour permits task-local HTML/CSS/GSAP
   UI authoring under its concrete leaf contract; helpers freeze/check/render,
    not dictate UI layout. Never edit managed scripts or frozen project source.
    Its screen_mode is recreate/supplied/capture: default recreate preserves v2,
    explicit modes use proposal-approved v3. Supplied and captured video remain
    real footage. Only VideoCreator's scoped wrapper records sanitized Web demos;
    no Assistant/browser/computer_use fallback. Native capture is unavailable.
   Shared clip helper:
   `python3 ${HERMES_SKILL_DIR}/scripts/clip-media.py --help` (from leaves,
   `python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py --help`).
4. Run `<QA>`. Append each finding to the job's `qa.md` before the next
   visual call. Samples are not whole-video verification. Use only the
   bounded looks the leaf names; do not loop on "one more to be sure".
5. Reply with `<Report>`, including failures and missing checks. Media
   generation budget counts attempts including failures; analysis has
   separate bounded calls. Never patch a managed skill at runtime.

</Run>
