---
name: create-tour
description: >-
  Author a bounded UI task walkthrough from reference screenshots, designs or
  text: recompose video-ready UI, animate actual visible states and follow the
  action with pointer/camera. Local HyperFrames source, proof frames and approved
  MP4, at most 60 seconds. Not URL capture, OS/browser automation, a general
  marketing film, image generation or speech synthesis.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "authored source project + preview frames; approved MP4/poster/review/qa.md"
    form:
      what_for:
        required: true
        type: text
        label: "what the viewer should learn or accomplish"
      audience:
        required: true
        type: text
        label: "who watches and what they already know"
      reference:
        required: false
        type: text
        label: "local files/directory or a textual UI description; URLs are context, not capture permission"
      flow:
        required: false
        type: text
        label: "approved semantic sequence and result, not precompiled steps.json"
      fidelity:
        required: false
        options: [faithful, simplified]
        label: "faithful (default) preserves product UI; simplified permits agreed explanatory recomposition, never invented product functions"
      frame:
        required: false
        other: true
        options: [macos, browser, ios, android, none]
        label: "decorative outer chrome, macos by default; never inferred OS behavior"
      style:
        required: false
        options: [flat, glass, outline]
        other: true
        references: references/styles/*.md
        label: "flat by default; presentation style or custom description, not permission to restyle faithful UI"
      background:
        required: false
        other: true
        options: [light, dark]
        label: "light by default; color or free-text decorative backdrop direction"
      backdrop:
        required: false
        type: image
        label: "optional existing local static image, preserve original and approve cropping"
      intro:
        required: false
        options: [title-reveal, ui-overview, result-first]
        other: true
        references: references/intro/*.md
        label: "ON by default (title-reveal); these are examples, free text is first-class; explicit none omits"
      outro:
        required: false
        options: [result-hold, overview-close, next-action]
        other: true
        references: references/outro/*.md
        label: "ON by default (result-hold); these are examples, free text is first-class; explicit none omits"
      duration:
        required: false
        type: int
        label: "total seconds including intro/outro, 1..60; default 20"
      destination:
        required: false
        options: [landscape, portrait]
        label: "1280x720 (default) or 720x1280; 30 fps"
      preview:
        required: false
        options: ["yes", "no"]
        label: "yes (default) stops at proof frames for approval; no authorizes local final render after checks"
      note:
        required: false
        type: text
---

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns the goal, audience,
   semantic flow, fidelity and choice approvals; you own task-local UI layout and
   motion implementation. Missing reference images are NOT a blocker when text
   specifies the UI. Never demand one screenshot per action or client-written
   steps JSON. A bare URL is context only: ask for the missing UI facts, not
   permission inferred from that URL. No capture, OS interaction, uploads,
   TTS, image generation, external skills or automatic dependency installation.
2. Read [authoring](references/authoring.md) before writing source. Read selected
   style examples: [flat](references/styles/flat.md),
   [glass](references/styles/glass.md), [outline](references/styles/outline.md).
   For known choices read the matching example:
   [title-reveal](references/intro/title-reveal.md),
   [ui-overview](references/intro/ui-overview.md),
   [result-first](references/intro/result-first.md),
   [result-hold](references/outro/result-hold.md),
   [overview-close](references/outro/overview-close.md),
   [next-action](references/outro/next-action.md).
   These are NOT exhaustive presets. Keep free text verbatim, implement its
   concrete beat locally, and record the interpretation alongside it. Never
   map it to the nearest known option. If unresolved, return ONE clarification
   or a concrete beat proposal to Creator before authoring. Only explicit
   `none` omits a boundary; blank/null is invalid, absence defaults ON.
3. Inventory surviving artifacts. For a persisted v1 project only, use the
   unchanged `scripts/tour.py snapshot|render` entry and
   [legacy steps](references/steps.md); its saved manifest/HTML stay untouched.
   A new v2 job does not reinterpret old forms or migrate old outputs.
4. Write UTF-8 `form.json` and your `contract.json` in job scratch; text goes
   through files, not Japanese argv. Author `index.html`, local assets and
   QA motion assertions in a fresh task-local source directory. Copy references
   needed to justify fidelity into that source bundle; preserve originals.
   Do not edit managed scripts to add a layout, UI action or custom intro/outro.
   Run local `hyperframes lint <source>` while authoring; then freeze:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/authored.py freeze --form <form.json> --contract <contract.json> --source <source> --project <deliver>/tour-project
   python3 ${HERMES_SKILL_DIR}/scripts/authored.py snapshot --project <deliver>/tour-project --out <deliver>/tour-preview
   ```

   Parent directories must already exist. Source/project/preview/final are
   separate directories; every output is a new child. Never clear a failed
   output. Freeze copies source and hashes, it does not choose or author UI.
5. Inspect proof frames against each expectation and record findings in
   `qa.md` before the next visual call. With `preview: yes`, return snapshots
   and wait for actual client approval of that exact project. Resume using:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/authored.py render --project <deliver>/tour-project --approved-preview <deliver>/tour-preview --out <deliver>/tour-final
   ```

   Creator's unchanged `intent: revise <preview>` + `preview: no` grants the
   resume; do not alter the saved form (it still says yes). Changed direction,
   content or source requires a fresh version and approval. An initial
   `preview: no` authorizes rendering without `--approved-preview`, but not
   skipping snapshot/visual QA. No self-approval. Long commands use
   `background: true` and polling within the tool's actual timeout.
6. Inspect decoded final frames, including boundary transitions, pointer
   contact, intermediate and final UI states. Append evidence and gaps to
   `qa.md`; one complete review pass plus one corrective pass, then report
   remaining defects. Do not loop, discard failed evidence or upload video.

</Procedure>

<QA>

- Check source intent against form: faithful UI is not blindly reskinned by
  chrome/background style. Simplification and illustrative functions are
  labeled and approved; no invented claims about a real product.
- Check every boundary, action and result with actual local frames. A modal
  appears, selection updates, typed text accumulates; moving a screenshot
  alone does not demonstrate authored UI capability. Pointer tips contact
  targets in the camera's coordinate space. Keep titles and result readable.
- `check.json` must contain runtime/layout/contrast results with nonzero text
  checks. A skipped audit is unverified. Inspect Japanese glyphs and wrapping
  at native size. Transition samples supplement held states, not replace them.
- Verify frozen hashes before/after commands, approved preview identity and
  fresh output paths. Full MP4 decode, codec, dimensions, fps and duration are
  mandatory. Review samples are not complete temporal or listening evidence.
- Runtime executes locally authored trusted code, not arbitrary downloaded
  HTML. Static helper checks are guardrails, NOT a JavaScript security sandbox.
  Review source for networking, external references, navigation and clocks
  before executing it. No external skill library is needed by these hands.

</QA>

<Report>

`create-tour`; source/project/preview/final paths; exact intro/outro directions
and concrete beats, including custom or explicit none; fidelity/simplifications;
RESULT JSON; QA evidence and unresolved checks; `spend: media generation 0`;
approval/revision handoff. Label direct local fixture renders as such, never
product-live or Creator-to-hands evidence. A preview is not an MP4 delivery.

</Report>
