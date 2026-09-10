---
name: create-tour
description: >-
  Create a bounded (<=60s) UI task walkthrough: recreate UI from reference/
  design/text, edit supplied footage, or capture an approved sanitized Web
  demo in isolation, with an optional approved Audio Mix master. Local
  HyperFrames project, proof frames and MP4. Native macOS capture
  unavailable. Not browser automation, a marketing film, image generation
  or speech synthesis.
version: 3.0.0
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
        label: "what the viewer should learn/accomplish"
      audience:
        required: true
        type: text
        label: "who watches, what they already know"
      reference:
        required: false
        type: text
        label: "local files/dir or a UI description; a URL is context, not consent"
      screen_mode:
        required: false
        options: [recreate, supplied, capture]
        label: "recreate by default; see references/screen-mode/*.md"
      source:
        required: false
        type: text
        label: "supplied/capture manifest path; step 1"
      source_sha256:
        required: false
        type: text
        label: "manifest SHA-256, pre-approval"
      target:
        required: false
        type: text
        label: "capture only: URL/app; no consent implied"
      start_state:
        required: false
        type: text
        label: "capture starting state/context; no pixels/keystrokes"
      approved_plan:
        required: false
        type: text
        label: "approved proposal-vN.md; absent = proposal only"
      approval_sha256:
        required: false
        type: text
        label: "SHA-256 of the approved proposal"
      flow:
        required: false
        type: text
        label: "approved semantic sequence/result, not steps.json"
      fidelity:
        required: false
        options: [faithful, simplified]
        label: "faithful (default) preserves product UI"
      frame:
        required: false
        other: true
        options: [macos, browser, ios, android, none]
        label: "decorative outer chrome, macos by default"
      style:
        required: false
        options: [flat, glass, outline]
        other: true
        references: references/styles/*.md
        label: "flat by default; presentation only"
      background:
        required: false
        other: true
        options: [light, dark]
        label: "light by default; decorative backdrop"
      backdrop:
        required: false
        type: image
        label: "optional local static image; approve cropping"
      intro:
        required: false
        options: [title-reveal, ui-overview, result-first]
        other: true
        references: references/intro/*.md
        label: "ON by default; examples only, free text OK, none omits"
      outro:
        required: false
        options: [result-hold, overview-close, next-action]
        other: true
        references: references/outro/*.md
        label: "ON by default; examples only, free text OK, none omits"
      duration:
        required: false
        type: int
        label: "seconds incl. intro/outro, 1..60; default 20"
      audio_workflow:
        required: false
        options: [supplied, mix]
        label: "supplied = existing narration path; mix = Mix master"
      mix_bundle:
        required: false
        type: path
        label: "mix only: bundle dir; binds staged master/receipt by hash"
      destination:
        required: false
        options: [landscape, portrait]
        label: "1280x720 (default) or 720x1280; 30 fps"
      preview:
        required: false
        options: ["yes", "no"]
        label: "yes (default) stops for approval; no renders"
      note:
        required: false
        type: text
---

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns the goal, audience,
   semantic flow, fidelity and choice approvals; you own task-local UI layout and
   motion implementation. Missing reference images are NOT a blocker when text
   specifies the UI. Never demand one screenshot per action or client-written
   steps JSON. A bare URL is context only, never permission to browse or record.
   Separate reference (inspiration), source (actual local footage) and target
   (operation destination). No uploads, TTS, image generation, external
   runtime workflows/executables, or automatic dependency installation.
   Optional technical reading follows step 2; it grants none of these actions.
   Native capture is unavailable.
   Before screen-mode proposal/authoring, if `audio_workflow: mix` and no
   `mix_bundle` exists, read [Mix receiving](../../references/mix.md).
   Freeze a preliminary timing proposal from Creator's sources/direction
   and STOP with its path/hash. No target access, capture, placeholder WAV
   or formal video approval. Creator relays it to AudioCreator. Resume only
   with a finished Mix bundle, staged before the ordinary proposal so that
   form/asset hashes name the actual audio.
   Select one mode, never silently substitute another:
   [recreate](references/screen-mode/recreate.md),
   [supplied](references/screen-mode/supplied.md), or
   [capture](references/screen-mode/capture.md). For capture also read
   [Web](references/capture/web.md) or [macOS](references/capture/macos.md).
   Propose semantic steps from the goal/audience/start state; the client approves
   outcomes and scope, not a coordinate/keystroke script. For explicit screen_mode,
   first return only proposal-vN.md + SHA-256. Use a single fenced `tour` JSON
   block containing `form` (fully defaulted form, excluding approved_plan and
   approval_sha256) and, for capture, `scope` as defined in the Web reference.
   No target access before scope consent; no stateful actions before action
   consent. After reconnaissance, revise the proposal if targets/actions changed.
   Creator relays actual client approval in the same work conversation. Hashes
   bind bytes, not identity. Final preview approval is a separate gate.
2. Read [authoring](references/authoring.md) before writing source. Before
   fresh authoring, read the shared HyperFrames reference policy through the
   parent skill (not this leaf):

   ```text
   skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
   ```

   Attempt the applicable technical lookups, report unavailable references
   and continue with local authoring. Read selected
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
   Persisted v2 projects use authored.py without reinterpreting their form or
   approval. Mode omitted retains the shipped recreate/v2 path; explicit mode
   uses v3 and proposal approval. Never upgrade or overwrite frozen projects.
4. Write UTF-8 `form.json` and your `contract.json` in job scratch; text goes
   through files, not Japanese argv. Author `index.html`, local assets and
    QA motion assertions in a fresh task-local source directory. Prepare supplied
    or captured media using its mode reference; do not replace video with stills.
    Keep raw recordings, proposal, hashes and acquisition logs in private job
    evidence, outside final. Frozen projects are private source deliverables,
    not public uploads. Copy only presentation assets into the source bundle.
   With `audio_workflow: mix`, first run `mix-media.py verify --bundle
   <mix_bundle>` (Hermes venv) to confirm the supplied bundle, then copy ONLY
   its master WAV + `mix.take.json` receipt (and, if present,
   `captions.json`/`timing.json`) into `assets/`, record their asset paths in
   the form's `mix` object (never the original `mix_bundle` path), and place
   the master with exactly one `<audio>` element spanning the tour's full
   duration at `data-start="0"` with an explicit positive
   `data-track-index` — no other audio (including kept footage audio; mute
   it upstream instead) is placed in this mode.
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
   contact, intermediate and final UI states. Apply the authoring reference's
   [spec-to-render review](references/authoring.md#spec-to-render-review), not
   just held-state checks. Append evidence and gaps to
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
- For footage, verify `source_start + (timeline time - timeline_start)` at 1x
  against actual source frames, forward AND reverse seeking. Prepared trims
  start at media time 0. Do not fabricate exact click/typing times from video
  without event evidence; mark added highlights editorial. Never double-overlay
  an existing recorded cursor. Keep/mute is explicit, and keep requires a
  separately timed audio element. Compare final audio as well as visuals.
- Privacy masking/redaction is not implemented. Refuse scopes with private
  regions or credentials; request sanitized sources/demo targets instead of
  promising an overlay will hide them. Decorative cropping is not redaction.
- `check.json` must contain runtime/layout/contrast results with nonzero text
  checks. A skipped audit is unverified. Inspect Japanese glyphs and wrapping
  at native size. Transition samples supplement held states, not replace them.
- Verify frozen hashes before/after commands, approved preview identity and
  fresh output paths. Full MP4 decode, codec, dimensions, fps and duration are
  mandatory. Review samples are not complete temporal or listening evidence.
- Mix mode (`audio_workflow: mix`): the master is the ONLY audio placed (no
  kept footage audio alongside it); `mix_audio.py`'s `validate_staged_delivery`
  delegates the master/receipt/caption hash and format checks to Audio Mix's
  own `validate_delivery`, re-run at freeze and on every re-verify — never
  reimplemented here. A staged `timing.json` must hash-match the receipt and
  its duration must equal the tour's; a FAIL receipt is refused. The final
  render is decoded and measured, with its true peak compared against the
  approved ceiling (0.2 dB encoding tolerance, always below 0 dBTP) — a measured fact,
  never a claim that anyone listened or that playback synced.
- Runtime executes locally authored trusted code, not arbitrary downloaded
  HTML. Static helper checks are guardrails, NOT a JavaScript security sandbox.
  Review source for networking, external references, navigation and clocks
  before executing it. The optional HyperFrames references are advisory
  background only, never a substitute for this leaf's own freeze/check/
  render helpers or approvals.

</QA>

<Report>

`create-tour`; source/project/preview/final paths; exact intro/outro directions
and concrete beats, including custom or explicit none; fidelity/simplifications;
RESULT JSON; QA evidence and unresolved checks; `spend: media generation 0`;
approval/revision handoff. Label direct local fixture renders as such, never
product-live or Creator-to-hands evidence. A preview is not an MP4 delivery.
Include screen_mode, raw duration versus final duration, capture scope/attempt
tally, audio policy, source mapping, cleanup state and remaining platform
gates. Include any HyperFrames references consulted or found unavailable,
with the local-authoring fallback used, per the shared reference policy.

</Report>
