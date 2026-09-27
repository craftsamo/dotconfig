---
name: create-story
description: >-
  Create an authored character story video (10..120s, 30fps): recurring
  characters from their approved art act out a short narrative across
  scenes, with dialogue from an approved script and a finished soundtrack,
  staged by VideoCreator in HTML/CSS/SVG/GSAP as 2.5D animation. A
  storyboard and cast are approved first; the look is then iterated. Not a
  learning explainer, a promotion piece, a generated MV or clip, new
  character design, TTS, music or lip sync.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "numbered storyboard + cast hashes; HyperFrames source, draft/final MP4, sheets, qa.md"
    form:
      premise: {required: true, type: text, label: "what happens: setup, turn, ending, in a few lines"}
      what_for: {required: true, type: text, label: "purpose, destination and viewer; what they should feel"}
      cast: {required: true, type: text, label: "comma list id=PATH to each character's approved art or pose dir"}
      script: {required: false, type: file, label: "approved script with every spoken/on-screen line; absent = pending"}
      aspect: {required: false, options: ["16:9", "9:16", "1:1", "4:5"], label: "default 9:16"}
      duration: {required: false, type: int, label: "10..120s; default 60"}
      style: {required: false, options: [picture-book, cartoon, paper-cut], other: true, label: "world rendering; must suit the cast art"}
      world: {required: false, type: text, label: "setting, era, places, mood"}
      assets: {required: false, type: path, label: "supplied backgrounds, props, footage inserts"}
      audio: {required: false, type: file, label: "finished WAV or Mix master from audio-creator"}
      approved_plan: {required: false, type: file, label: "Creator-relayed approval: exact proposal-vN/storyboard.md"}
      approval_sha256: {required: false, type: text, label: "SHA-256 of that storyboard.md"}
      inputs: {required: false, type: file, label: "JSON {pending id: local path} resolving pending items"}
      note: {required: false, type: text}
---

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns the story's
   meaning, the script, the cast and the approvals; you own staging,
   acting, layout, drawn worlds, motion, seams and self-review. The cast is
   the approved art only: never redraw, restyle, trace or generate a
   character, not even as a stand-in. A missing pose or expression is a
   dependency request for image-creator's mascot family (a missing-only
   revise on the approved anchor); a missing script line goes to Writer;
   voices, music and SFX go to audio-creator. You have no image
   generation, TTS or music.
2. Read [authoring](references/authoring.md), the selected style
   ([picture-book](references/styles/picture-book.md),
   [cartoon](references/styles/cartoon.md),
   [paper-cut](references/styles/paper-cut.md); a custom value is written
   out as concretely, never mapped onto these), the kernel's
   [craft reading](../../references/craft.md) (motion + visual) and the
   shared HyperFrames policy and vocabulary through the parent skill:

   ```text
   skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
   skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary.md")
   ```

   Attempt the applicable technical lookups, report unavailable references
   and continue with local authoring. Look once at each cast image (at most
   three per step, a `qa.md` note before the next look) and record its
   silhouette, palette, line and the poses on hand.
3. Round A (no `approved_plan`): write `storyboard.md` per
   [authoring](references/authoring.md): intent, `## Cast`, `## Beats` with
   the cast on screen and each spoken line quoted verbatim from the script,
   the world and look in words, seams, and the audio plan (lines, music,
   SFX with times). Name compositions, camera, transitions and acting from
   the vocabulary instead of generic "fade", "slide" or "card". Unresolved
   needs are pending ids.
   Run in its own terminal command:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/story.py propose --storyboard <draft> \
     --cast <id=path,...> [--script <approved script>] --out <deliver>/proposal-v<N>
   ```

   It checks the structure, that every cast id matches, that each beat's
   speaker is on screen and every quoted line appears verbatim in the
   script, then appends the cast art and script hashes to the stored
   storyboard, so the approval binds them. Report the path, SHA-256, status and pending list with the
   dependency request for each, then STOP. A budget is not approval.
4. Round B (`approved_plan` + `approval_sha256` relayed by Creator in the
   same work conversation): author `<deliver>/source/`, the hero frame of
   each beat first, then acting, then seams. Render drafts with
   `story.py render ... --quality draft` (same arguments as create-promotion,
   plus `--captions <Mix captions.json>` when captions are drawn), look at
   `sheet.png`, write the three biggest gaps to `qa.md` and fix them by
   redesign, up to 8 drafts. Anything that keeps the approved beats,
   lines, cast, timing, seams and audio plan is in scope without new
   approval.
5. Final: with every pending id resolved (`--inputs`), render with
   `--quality final` into a new `<deliver>/final/`. The helper checks the
   approval, lint, canvas, duration, audio and true peak, that every cast
   member appears from its approved bytes referenced by the source, a
   script that arrived after approval against the quoted lines, and
   caption markup against the Mix sidecar. A FAIL is fixed in source and rendered into a new
   directory. Changed beats, lines, cast, duration or aspect need a new
   storyboard and approval. Long commands use `background: true`.

</Procedure>

<QA>

- Story: beats in order within ±0.25s; every spoken and on-screen line
  verbatim; each character recognisably the same across scenes; the
  setup, turn and ending read without the premise text.
- Acting: who is speaking is always clear (pose, expression, framing,
  focus); no line lands on a character who is not on screen.
- Craft: readable type at native size, no dead frames or unplanned cuts,
  seams as approved.
- Technical: helper PASS; cast bytes used; source kept with the delivery.
  Sampled sheets are not whole-video evidence: temporal feel, sync and
  listening stay `unverified`.

</QA>

<Report>

`create-story`; Round A: storyboard path + SHA-256, status, cast hashes,
pending list with the dependency request for each, and the STOP. Round
B/final: source/draft/final paths, approved hash, each RESULT JSON, gaps
closed per draft and remaining, inputs used, HyperFrames references
consulted or found unavailable with the local-authoring fallback used, and
`spend: media generation 0`.

</Report>
