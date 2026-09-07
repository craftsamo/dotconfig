---
name: create-ad
description: >-
  Create a short authored ad (default portrait 9:16 1080x1920, or 16:9/1:1/4:5,
  30fps) from client-approved product, audience, message, CTA and optional
  supplied assets/audio. First return an unspent content plan for approval;
  author and freeze source only after Creator relays approval of that exact
  plan. Local HyperFrames project, proof frames and MP4. Not video/image
  generation, TTS, capture, or a claims fact-checker.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: free
    output: "authored MP4 at the approved ratio (9:16/16:9/1:1/4:5, 30fps) + frozen source + proof frames/QA"
    form:
      product:
        required: true
        type: text
        label: "what is being advertised"
      audience:
        required: true
        type: text
        label: "who watches and what they already know or need"
      message:
        required: true
        type: text
        label: "the single approved headline claim/benefit; must appear verbatim in the plan's copy"
      cta:
        required: true
        type: text
        label: "the single approved call to action; must appear verbatim in the plan's copy, held >=2s"
      aspect:
        required: false
        options: ["9:16", "16:9", "1:1", "4:5"]
        label: "output canvas ratio; default 9:16. Fixed dims per ratio (9:16=1080x1920, 16:9=1920x1080, 1:1=1080x1080, 4:5=1080x1350), no arbitrary size, no crop/scale of another ratio's layout"
      assets:
        required: true
        type: path
        label: "local directory of approved product/logo/audio/video assets; always ends up holding at least the vendored GSAP runtime files, even for a text-only ad"
      claims:
        required: false
        type: text
        label: "authoritative supporting evidence and restrictions for any claim-role copy; not fact-checked here, only required nonempty when used"
      theme:
        required: false
        options: [office]
        other: true
        references: references/themes/*.md
        label: "world/setting vocabulary; the listed default is a starting point, never a fixed preset"
      theme_detail:
        required: false
        type: text
        label: "override motifs, palette, materials or light; client choices replace conflicting theme defaults"
      style:
        required: false
        options: [bold-graphic]
        other: true
        references: references/styles/*.md
        label: "presentation treatment; a described look is equally valid"
      direction:
        required: false
        options: [claim-led]
        other: true
        references: references/direction/*.md
        label: "how message/claim/cta are staged and paced; free text is first-class"
      audio:
        required: false
        type: file
        label: "already-finished standalone WAV only; no TTS/synthesis here"
      reference:
        required: false
        type: file
        label: "local reference/report for inspiration or the claim's evidence; never uploaded"
      duration:
        required: false
        type: int
        label: "total seconds, 6..30; default 15"
      approved_plan:
        required: false
        type: file
        label: "Creator-relayed approval: the exact approved plan.json; absent means proposal only, no source authoring"
      approval_sha256:
        required: false
        type: text
        label: "SHA-256 of the exact plan.json the client approved; required with approved_plan"
      preview:
        required: false
        type: path
        label: "client-approved preview folder from snapshot; required before render"
      preview_sha256:
        required: false
        type: text
        label: "SHA-256 of that approved preview.json; required with preview"
      note:
        required: false
        type: text
---

<Procedure>

1. Work only in `specialist_call(kind="work")`. Creator owns product meaning,
   audience, message/CTA wording and PV routing; you own concrete layout,
   timeline and QA within the approved plan. Missing supplied product/logo/
   audio/video assets are not a blocker for a text-only ad — but `assets/`
   itself is never actually empty: the vendored GSAP runtime files always
   belong in the plan's asset map. No video/image generation, TTS, capture or
   external runtime skills. Output canvas is one of four fixed ratios —
   9:16 (1080x1920, default), 16:9 (1920x1080), 1:1 (1080x1080), 4:5
   (1080x1350) — always 30fps; do not invent other dimensions, and never
   crop or scale a layout authored for one ratio into another.
2. Read [authoring](references/authoring.md) for the exact `plan.json` schema
   and CLI walkthrough before writing anything. For known choices read the
   matching short reference: [office](references/themes/office.md),
   [bold-graphic](references/styles/bold-graphic.md),
   [claim-led](references/direction/claim-led.md). These are concrete starting
   points, not an exhaustive preset menu; a custom `other: true` value is
   implemented locally, verbatim, and never silently mapped onto a listed
   option. If direction is ambiguous, return one clarification or a concrete
   beat proposal before authoring.
3. Round A (no `approved_plan`): author a `plan.json` per the schema in
   [authoring](references/authoring.md) — exact copy rows (id/text/role/
   start/end) that include the client's literal `message` and `cta` text,
   any approved `claims` backing a `claim`-role row, the complete asset SHA-256
   map (including the vendored GSAP files you will copy in), and ordered proof
   `samples` covering the first/last visible frame and a moment inside every
   copy hold. Compute and report its SHA-256; do not author `index.html` or
   call the helper's `freeze` yet. STOP for actual client approval in the same
   work conversation; the budget/plan is not itself approval.
4. Round B requires both `approved_plan` and `approval_sha256` from Creator.
   Author `index.html` and local assets in a fresh task-local source
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
   become local files under `assets/`; any WAV plays at unity volume, unmuted,
   with explicit `data-start`/`data-duration`; any MP4 is muted with the same
   explicit timing. No autoplay, clocks, randomness, remote requests, active
   embeds/event handlers or JS media playback/seek control — HyperFrames owns
   the timeline. Only PNG/JPG/WebP logos/images are accepted this version; ask
   the client to supply a raster export for an SVG logo. Run local
   `hyperframes lint <source>` while authoring, then freeze:

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
- Audio/video policy: audio-creator or client-finished WAV only, at unity
  volume, never synthesized here; muted video-in-video only; timing windows
  match declared placements against actual decoded media, forward and reverse.
- Verify frozen hashes before/after commands, the approved plan/preview
  identity, and that outputs are fresh directories outside source/project/
  preview. Full MP4 decode, codec, dimensions, fps, duration and audio
  presence-vs-plan are mandatory. Sampled review frames are not complete
  temporal or listening evidence — leave `qa.json`'s semantic/temporal/audio
  fields as pending/sampled/unverified until a human visual/listening pass.
- Runtime executes locally authored trusted code, not arbitrary downloaded
  HTML. Static helper checks are guardrails, NOT a JavaScript security
  sandbox; review source for networking, external references, navigation and
  clocks before executing it. No external skill library is needed here.

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

</Report>
