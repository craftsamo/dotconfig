---
name: create-explainer-video
description: >-
  Create an explanation from approved words and supplied media, with no character,
  a bust presenter or a full-body presenter. Propose first; render only after
  content and preview approvals. Not UI tours, ads, music videos, media generation,
  automatic lip-sync inference or rig creation. Engine is an explicit proposal
  choice: v1 HyperFrames or v2 Motion Canvas; never a silent switch.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "numbered proposal + hashes; approved source/preview/MP4/poster/QA"
    form:
      topic:
        required: true
        label: "what is explained"
      audience:
        required: true
        label: "viewer and prior knowledge"
      learning_goal:
        required: true
        label: "what the viewer should understand"
      script:
        required: false
        type: file
        label: "approved spoken words; absent may be pending"
      framing:
        required: true
        options: [none, bust, full]
        label: "explicit choice; unset is not none"
      performance:
        required: false
        options: [still, puppet, animated]
        label: "body acting; propose when unset"
      lip_sync:
        required: false
        options: ["off", cues, baked]
        label: "bust: propose cues; never silently downgrade"
      character_assets:
        required: false
        type: path
        label: "caller-selected files/directory, not upload consent"
      narration:
        required: false
        type: path
        label: "finished WAV or Mix bundle; absent is not silent"
      theme:
        required: false
        options: [studio, classroom, workbench, abstract-space]
        other: true
        references: references/themes/*.md
        label: "world; default studio; custom OK"
      style:
        required: false
        options: [flat-vector, paper-cut, mixed-media]
        other: true
        references: references/styles/*.md
        label: "medium; default flat-vector; preserve supplied identity"
      direction:
        required: false
        options: [mechanism, process, comparison, misconception, worked-example]
        other: true
        references: references/direction/*.md
        label: "teaching method; default mechanism; mixes OK"
      renderer:
        required: false
        options: [hyperframes, motion-canvas]
        label: "default hyperframes (v1); motion-canvas (v2) is an explicit choice"
      duration:
        required: false
        type: int
        label: "1..180s; proposal estimate, then actual master timing"
      aspect:
        required: false
        options: ["16:9", "9:16"]
        label: "default 16:9; 1280x720 or 720x1280, 30fps"
      pending:
        required: false
        type: text
        label: "missing inputs, intended producers and next approvals"
      must_keep:
        required: false
        label: "non-negotiable words, identity, actions or restrictions"
      approved_plan:
        required: false
        type: file
        label: "approved proposal-vN/proposal.md"
      approval_sha256:
        required: false
        label: "exact proposal SHA-256"
      preview:
        required: false
        type: path
        label: "approved preview directory"
      preview_sha256:
        required: false
        label: "exact preview.json SHA-256"
      note:
        required: false
        type: text
---

<Procedure>

1. Always use a work session. Creator settles meaning, audience, learning goal
   and client choices. You own the visual explanation, not new facts or rewritten
   dialogue. Use Writer's approved script inputs and Researcher's grounding when
   needed, relayed through Creator. Missing script, voice or art may enter the
   preliminary proposal as dependencies; ask Creator for them, never synthesize
   or call another hands profile directly. A budget is not approval.
2. Confirm character intent using [character](references/character.md): none,
   existing, or new, then framing/performance/lip_sync. For no-character mode,
   use still/off without character assets; narration can still be present. For
   bust, propose cues plus expression changes; for full, preserve the requested
   acting level. Still/puppet uses supplied images, reviewed cues and local
   authored motion; animated uses a finished supplied MP4. No automatic phoneme
   analysis, image-to-rig conversion or natural acting generation is implemented.
   Unknown or absent runtime capability is pending, never a false success or a
   switch to still/off. Renderer is an explicit engine choice, preserved once
   made: v1 HyperFrames suits HTML/UI or media-oriented compositions, v2
   Motion Canvas suits reactive diagrams, algorithms and Canvas-based
   explanation — never a silent switch on failure.
3. Asset discovery belongs to Creator before handoff. Use the specified files
   first. A named collection is resolved only inside the caller-known workspace;
   ambiguous candidates go back to the client, never a whole-home scan. Store
   concrete paths and identity only in private job files, not in managed skills,
   tests, examples or config. Preserve originals; stage selected copies only,
   using neutral role names such as body, mouth-rest and narration rather than
   private names. Proposals remain private job evidence, not public-safe exports.
   Existing identity plus missing poses means a missing-only production request,
   not a new character. New art/voice needs separate Creator-brokered approval
   and budget through ImageCreator/AudioCreator. An unreadable supplied path is
   an error, not permission to invent a replacement or silently generate.
4. Read [authoring](references/authoring.md) before preparing the internal spec.
   When `renderer: motion-canvas`, also read
   [motion-canvas](references/motion-canvas.md) before authoring `scene.tsx`.
   Load only the selected theme: [studio](references/themes/studio.md),
   [classroom](references/themes/classroom.md), [workbench](references/themes/workbench.md),
   [abstract-space](references/themes/abstract-space.md); style:
   [flat-vector](references/styles/flat-vector.md), [paper-cut](references/styles/paper-cut.md),
   [mixed-media](references/styles/mixed-media.md); direction:
   [mechanism](references/direction/mechanism.md), [process](references/direction/process.md),
   [comparison](references/direction/comparison.md), [misconception](references/direction/misconception.md),
   [worked-example](references/direction/worked-example.md). Expand each choice
   into concrete space, materials, visual relationships and changes. Free text
   overrides defaults, never maps to the nearest option. No theme/style/character
   combination menu. The same explanation without a character needs intentional
   recomposition, not an empty presenter slot.
5. Round A: author `spec.json` per the reference, not HTML. Preserve exact spoken
   and on-screen words. Every unit names its learning goal and before/change/after
   states; every important change has a proof sample. User-facing forms do not
   require the client to author JSON, cue schedules or a storyboard. Refer
   unapproved/missing script content to Writer through Creator; do not draft
   substitute dialogue yourself. Estimates are not measured audio timings.
   Genuinely missing asset references are null with explicit dependency requests;
   never use invented future paths/hashes. Include unsupported renderer or
   character-production work in pending. Run only:

   ```sh
   ~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python ${HERMES_SKILL_DIR}/scripts/explainer.py propose --spec <spec.json> --out <deliver>/proposal-v1
   ```

   Choose the next unused proposal number on revision. This validates/stages
   existing local inputs, not media generation or video rendering. Report
   pending-inputs or awaiting-approval and STOP. Pending is a useful preliminary
   proposal, not an executable release. When dependencies arrive, revise the
   timing/spec and create a new numbered proposal with actual files and hashes.
   AudioCreator owns speech and Mix; use the real master length, no hidden speedup.
6. Round B: require Creator-relayed client approval of that exact executable
   proposal in the same work conversation. Check the helper's proposal hash;
   never manufacture approval. For HyperFrames only, read the optional policy
   through its parent skill before fresh authoring:

   ```text
   skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
   ```

   Missing external documentation is reported and local authoring continues;
   missing actual inputs/runtime or failed checks do not receive that fallback.
   Copy the proposal's assets unchanged into fresh source. HyperFrames uses
   one seekable HTML/CSS/GSAP composition and its generated mouth track.
   Motion Canvas instead uses `scene.tsx` and `scene.meta` per
   [Motion Canvas](references/motion-canvas.md), with no GSAP or generated
   mouth-track asset and no HyperFrames technical-policy lookup. No network,
   external runtime workflows, installs, upgrades, capture or new synthesis.
   The helpers do not generate a layout or sandbox arbitrary downloaded code.
   Use the reference's freeze then snapshot commands, never a direct render.
7. Compare preview frames to unit expectations, approved words and character
   intent. Return the exact preview hash and wait for client approval. Resume
   with the reference's render command using that approved preview, never a
   recomputed self-approved hash. Changed audio, art, text, framing, performance
   or renderer requires a new proposal/source/preview and approvals. A frozen
   render-only resume reuses its evidence; it does not reauthor from new recipes.
8. Inspect decoded final frames, including explanation changes, mouth contacts
   and phrase boundaries. Record findings in `qa.md` before the next look. Use
   one complete sample review plus one corrective review; stop and report remaining
   gaps rather than looping. Corrections preserve client requirements and original
   files. Never auto-promote new assets into a user's canonical collection.

</Procedure>

<QA>

- Understanding: inspect before/change/after evidence, not just a diagram's
  presence. Labels, arrows, comparisons and causal order match approved facts;
  unverified factual claims remain unverified, however attractive the result.
- Words: narration units preserve the supplied script, displayed copy is exact,
  Japanese glyphs and wrapping are readable, and no instruction leaks into copy.
  ASR text is not a replacement script; subtitle timings remain estimated unless
  separately reviewed. Check whole phrases and reading holds, not just one frame.
- Contrast: report the actual engine's audit status. Motion Canvas requires
  visual contrast/readability review; an absent automated contrast check is
  never a pass. Preserve that gap until a real visual review addresses it.
- Character: framing, identity and acting match the plan. Image translation or
  pose swaps are not proof of smooth body performance. Mouth image alignment and
  occlusion need visual review; same dimensions alone do not establish alignment.
  Cues originate from dry speech, then use the approved timeline offset. A hash
  binds source identity, not phonetic accuracy. Never call RMS open/close exact
  lip-sync. Baked sync receipts likewise do not prove observed mouth/speech fit.
- Sound: only the approved master plays, never dry stems alongside a Mix master.
  Measure final format/duration/peak and review speech dominance if listening is
  available. Waveforms, ASR and still frames do not constitute listening.
- Integrity: content and preview approvals, asset hashes, fresh output paths,
  full decode, dimensions, fps and duration must pass. Automated checks are
  structural, not a JavaScript sandbox or a complete temporal/factual review.
- Evidence: consulted/unavailable technical references and fallback are recorded.
  Missing mandatory content/performance cannot be relabeled as optional-doc absence.

</QA>

<Report>

Round A: `create-explainer-video / pending-inputs` or `awaiting-approval`, proposal
path/hash, concrete theme/style/direction, unit progression, character choices,
missing inputs/producers/next approvals, `can_render`, and zero media generation.
A pending proposal does not authorize the missing production steps.

Preview: frozen project, proof frames, preview.json hash, findings and approval
request. Final: source/project/MP4/poster/review/QA paths, actual formats/duration,
PASS/FAIL/UNVERIFIED findings, engine and contrast-audit status, remaining visual
review gaps, lip-sync/listening limitations, optional-reference
gaps with the local-authoring fallback used, and `spend: media generation 0`
(component production has separate receipts).
Required unfinished content or failed QA prevents a completed-video claim. A
client may accept disclosed residual review gaps, but their evidence remains
UNVERIFIED. Label synthetic local fixtures as tests, never live handoff evidence.

</Report>
