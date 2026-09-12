---
name: create-ad
description: >-
  Create a short authored ad (default portrait 9:16, or 16:9/1:1/4:5, 30fps)
  from client-approved product, audience, message, CTA and optional supplied
  assets/audio, or an approved Audio Mix master. Returns an unspent content
  plan for approval first; authors/freezes source only after Creator relays
  approval of that exact plan. Local HyperFrames project, proof frames and
  MP4. Not video/image generation, TTS, capture, or a claims fact-checker.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "authored MP4 at approved ratio + frozen source + proof frames/QA"
    form:
      product: {required: true, type: text, label: "what is being advertised"}
      audience: {required: true, type: text, label: "who watches, what they already know/need"}
      message: {required: true, type: text, label: "single approved headline claim/benefit; must appear verbatim in plan copy"}
      cta: {required: false, type: text, label: "final: exact CTA held >=2s; study: omit"}
      purpose: {required: false, options: [final, study], label: "default final; study is separately approved, never final media"}
      question: {required: false, type: text, label: "study only: one visual/motion question"}
      aspect: {required: false, options: ["9:16", "16:9", "1:1", "4:5"], label: "output canvas ratio, default 9:16 (fixed dims per ratio, see ad-render.py); no arbitrary size or cross-ratio crop/scale"}
      assets: {required: true, type: path, label: "local dir of approved product/logo/audio/video assets; always includes vendored GSAP files, even text-only"}
      claims: {required: false, type: text, label: "evidence/restrictions for claim-role copy; not fact-checked, required only if used"}
      theme: {required: false, options: [office], other: true, references: references/themes/*.md, label: "world/setting vocabulary; listed default is a starting point, not a fixed preset"}
      theme_detail: {required: false, type: text, label: "override motifs/palette/materials/light; replaces conflicting theme defaults"}
      style: {required: false, options: [bold-graphic], other: true, references: references/styles/*.md, label: "presentation treatment; a described look is equally valid"}
      direction: {required: false, options: [claim-led], other: true, references: references/direction/*.md, label: "how message/claim/cta stage and pace; free text is first-class"}
      audio: {required: false, type: file, label: "supplied only: finished WAV, or JSON list of <=16 {source, start} cues; plays from its start, pre-edited; no TTS here"}
      audio_workflow: {required: false, options: [supplied, mix], label: "supplied (default) = audio field; mix = approved Mix master via mix_bundle"}
      mix_bundle: {required: false, type: path, label: "mix only: bundle dir to verify+stage; plan binds staged master/receipt by hash"}
      reference: {required: false, type: file, label: "local reference/report for inspiration/claim evidence; never uploaded"}
      duration: {required: false, type: int, label: "final 6..30s (default 15); study 1..10s"}
      approved_plan: {required: false, type: file, label: "Creator-relayed approval: exact approved plan.json; absent = proposal only"}
      approval_sha256: {required: false, type: text, label: "SHA-256 of the approved plan.json; required with approved_plan"}
      preview: {required: false, type: path, label: "client-approved preview folder from snapshot; required before render"}
      preview_sha256: {required: false, type: text, label: "SHA-256 of the approved preview.json; required with preview"}
      note: {required: false, type: text}
---

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns product meaning,
   audience, message/CTA wording and PV routing; you own concrete layout,
   timeline and QA within the approved plan. Missing supplied product/logo/
   audio/video assets are not a blocker for a text-only ad — but `assets/`
   itself is never actually empty: the vendored GSAP runtime files always
   belong in the plan's asset map. No video/image generation, TTS, capture,
   or external runtime workflows/executables. Optional technical reading
   follows Round B; it grants none of these actions. Output canvas is one
   of four fixed ratios —
   9:16 (1080x1920, default), 16:9 (1920x1080), 1:1 (1080x1080), 4:5
   (1080x1350) — always 30fps; do not invent other dimensions, and never
   crop or scale a layout authored for one ratio into another.
   A final ad still requires `cta`; absence never selects study implicitly.
   Only an explicit `purpose: study` selects [diagnostic study](references/study.md).
   Read it before proposing that unit; it preserves both approval rounds and
   produces only study.mp4. Study rejects Mix mode and needs explicit duration
   and question. Use approved supplied WAV cues if audio is part of the study.
   For studies, use that reference's schema and freeze-study/render-study command
   substitutions below; all remaining source and approval checks still apply.
   Before Round A, if `audio_workflow: mix` and `mix_bundle` is absent,
   read [Mix receiving](../../references/mix.md). Author/freeze a timing
   proposal from Creator's source inventory and video direction; return
   its path/hash and STOP. No HTML, dummy audio, formal plan approval or
   rendering. Resume Round A only after Creator supplies the finished Mix;
   stage its real bytes BEFORE computing the plan's asset hashes.
2. Read [authoring](references/authoring.md) for the exact `plan.json` schema
   and CLI walkthrough before writing anything. For known choices read the
   matching short reference: [office](references/themes/office.md),
   [bold-graphic](references/styles/bold-graphic.md),
   [claim-led](references/direction/claim-led.md). These are concrete starting
   points, not an exhaustive preset menu; a custom `other: true` value is
   implemented locally, verbatim, and never silently mapped onto a listed
   option. If direction is ambiguous, return one clarification or a concrete
   beat proposal before authoring.
3. Round A (no `approved_plan`): for final purpose author `plan.json` per the schema in
   [authoring](references/authoring.md) — exact copy rows (id/text/role/
   start/end) that include the client's literal `message` and `cta` text,
   any approved `claims` backing a `claim`-role row, the complete asset SHA-256
   map (including the vendored GSAP files you will copy in), and ordered proof
   `samples` covering the first/last visible frame and a moment inside every
   copy hold. Compute and report its SHA-256; do not author `index.html` or
   call the helper's `freeze` yet. STOP for actual client approval in the same
   work conversation; the budget/plan is not itself approval.
   Before reporting a ready proposal, run `ad-render.py preflight --plan
   <plan.json> --assets <existing-assets-dir>` through the same Python command
   used below. It reads the schema and exact asset inventory (including suffix,
   size and vendor checks), writes nothing and executes no source. Preserve its
   unverified checks: passing preflight does not approve or prove a render.
4. Round B requires both `approved_plan` and `approval_sha256` from Creator.
   Before fresh authoring, read the shared HyperFrames reference policy
   through the parent skill (not this leaf):

   ```text
   skill_view(name="video-creator-pipeline", file_path="references/hyperframes.md")
   ```

   Attempt the applicable technical lookups, report unavailable references
   and continue with local authoring. Author
   `index.html` and local assets in a fresh task-local source
   directory: one standalone `#root` with
   `data-composition-id="ad" data-start="0" data-width="<plan width>"
   data-height="<plan height>" data-duration="<duration>" data-fps="30"`
   matching the approved plan's `aspect` (or 1080x1920 when `aspect` is
   absent), local
    `gsap.min.js`, `GSAP-LICENSE.txt` and `gsap-provenance.json` in the source
    assets directory, copied from
   this hands' existing vendored tour assets
   (`../tour/assets/`), and one element per approved copy row whose `id`
   matches the plan and whose exact rendered plain text matches the plan's
   copy text (nested spans may only be whitespace-normalized, never reworded).
   Every other visible text outside `<script>/<style>/<title>` must also
   belong to a declared copy id — no silent additions. Supplied `assets`
   become local files under `assets/`; with `audio_workflow: supplied`
   (default), any WAV plays at unity volume, unmuted, with explicit
   `data-start`/`data-duration` — up to 16 WAVs total, each placed by exactly
   one `<audio>` element (a repeated sound at another time needs its own
   separately approved local asset copy, never the same `src` placed twice);
   more than one placed WAV requires an explicit, distinct positive
   `data-track-index` per file (one legacy placement may omit it). With
   `audio_workflow: mix`, first run `mix-media.py verify --bundle
   <mix_bundle>` (via the Hermes venv) to confirm the supplied bundle, then
   copy ONLY its master WAV + `mix.take.json` receipt (and, if present,
   `captions.json`/`timing.json`) into `assets/`, record their asset paths in
   the plan's `mix` object (never the original `mix_bundle` path), and place
   the master with exactly one `<audio>` element spanning the full ad
   duration at `data-start="0"` — no other WAV asset or placement is allowed
   in this mode. Any MP4 is muted with the same explicit timing. No autoplay,
   clocks, randomness, remote requests, active embeds/event handlers or JS
   media playback/seek control — HyperFrames owns the timeline. Only
   PNG/JPG/WebP logos/images are accepted this version; ask the client to
   supply a raster export for an SVG logo. Run local `hyperframes lint
   <source>` while authoring, then freeze:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-render.py freeze \
     --source <source> --plan <deliver>/plan.json --approval-sha256 <hash> --project <deliver>/ad-project
   ```

   Parent directories must already exist. Source/project/preview/final are
   separate directories; every output is a new child, never inside another.
   Never clear a failed output. Freeze copies and hashes source; it does not
   choose or author copy/layout, and it re-verifies the source is unchanged
   after copying.
5. Snapshot to get proof frames and a preview hash for approval:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-render.py snapshot \
     --project <deliver>/ad-project --out <deliver>/ad-preview
   ```

   Inspect every proof frame against its `expect` text and record findings in
   `qa.md` before the next visual call. Return snapshots and the printed
   `preview_sha256`, then wait for actual client approval of that exact
   preview folder. Hashes bind approval bytes, not caller identity; Creator
   relaying approval in the same work conversation is what grants the resume.
6. Resume only with both the approved preview folder and its exact SHA-256:

   ```sh
   uv run --no-project --with Pillow python ${HERMES_SKILL_DIR}/scripts/ad-render.py render \
     --project <deliver>/ad-project --approved-preview <deliver>/ad-preview \
     --approval-sha256 <preview-hash> --out <deliver>/ad-final
   ```

   Both arguments are required; there is no bypass. Changed direction, copy,
   claims or source requires a fresh plan/source/project/preview and a new
   approval. No self-approval. Long commands use `background: true` and
   polling within the tool's actual timeout.
7. Inspect decoded final frames, including every copy hold, the CTA hold and
   the boundary transitions between them. Append evidence and gaps to
   `qa.md`: one complete review pass plus one corrective pass, then report
   remaining defects. Do not loop, discard failed evidence or upload video.

</Procedure>

<QA>

For an explicit study, judge its named question and real message/copy; CTA-only
requirements below apply only to final ads. All other evidence and safety checks
remain required. A successful diagnostic is not an accepted final advertisement.

- Plan-to-render fidelity: the message and CTA appear verbatim on screen for
  their declared hold; any claim-role text matches the plan and traces to the
  supplied `claims` field. This checker verifies exact copy text and timing
  structure only — it is not a fact-checker and never certifies a claim as
  true, "verified" or "No.1"; only client-supplied authoritative statements
  may back a claim, and none may be invented.
- CTA is readable for its full >=2s declared hold in the decoded frames, not
  only structurally timed. Compare native-size text, wrapping and contrast at
  actual render resolution, including Japanese glyphs.
- No unauthored/undeclared visible text appears; the static ledger check is
  necessary but not sufficient — confirm by eye that nothing was silently
  added, dropped or reworded between plan and rendered frame.
- Supplied assets are used as supplied, never substituted or reskinned beyond
  the approved theme/style/direction. Faithful product/logo representation;
  simplified/illustrative elements are labeled and approved, never presented
  as real product functionality.
- Audio/video policy: audio-creator or client-finished WAV only (up to 16
  tracks, one distinct `data-track-index` per WAV when more than one is
  placed, never the same asset reused for a repeated sound), at unity
  volume, never synthesized here; muted video-in-video only; timing windows
  match declared placements against actual decoded media, forward and
  reverse. A multi-track final mix is additionally decoded and measured
  (`loudnorm`) — measurement only, never silent gain correction. A short/
  sparse SFX-style ad legitimately measures an unmeasurable integrated
  loudness alone (reported with a warning, not a failure); only an
  undecodable, entirely blank/silent, or clipping (true peak >=0 dBTP)
  result is a defect, fixed by reducing gain (e.g. a fresh edit-sfx pass) or
  revising the placement timing — never a "ducking"/automatic mixing
  capability this leaf does not have.
- Mix mode (`audio_workflow: mix`): the master is the ad's ONLY audio (no
  stems alongside it); `mix_audio.py`'s `validate_staged_delivery` delegates
  the master/receipt/caption hash and format checks to Audio Mix's own
  `validate_delivery`, re-run at freeze and again on every re-verify — never
  reimplemented here. A staged `timing.json` must hash-match the receipt's
  own record and its duration must equal the ad's; a FAIL receipt is refused.
  The single-WAV final render is also decoded and measured, and its true
  peak is compared against the approved ceiling (0.2 dB encoding tolerance,
  always below 0 dBTP) — a measured fact, never a claim that anyone listened.
- Verify frozen hashes before/after commands, the approved plan/preview
  identity, and that outputs are fresh directories outside source/project/
  preview. Full MP4 decode, codec, dimensions, fps, duration and audio
  presence-vs-plan are mandatory. Sampled review frames are not complete
  temporal or listening evidence — leave `qa.json`'s semantic/temporal/audio
  fields as pending/sampled/unverified until a human visual/listening pass.
- Runtime executes locally authored trusted code, not arbitrary downloaded
  HTML. Static helper checks are guardrails, NOT a JavaScript security
  sandbox; review source for networking, external references, navigation and
  clocks before executing it. The optional HyperFrames references are
  advisory background only, never a substitute for this leaf's own
  freeze/snapshot/render helpers or approvals.

</QA>

<Report>

`create-ad`; Round A: plan path + SHA-256, expanded theme/style/direction
choices including custom or explicit interpretations, and the STOP for
approval — no source authored yet. Round B: source/project/preview/final
paths; approved plan/preview hashes; RESULT JSON from each helper call; QA
evidence and unresolved checks; `spend: media generation 0`. Label direct
local fixture renders as such, never client-live or claim-verified evidence.
A preview is not an MP4 delivery. Include raw duration versus final duration,
asset inventory, audio policy, cleanup state and remaining platform gates.
Include any HyperFrames references consulted or found unavailable, with the
local-authoring fallback used, per the shared reference policy.

</Report>
