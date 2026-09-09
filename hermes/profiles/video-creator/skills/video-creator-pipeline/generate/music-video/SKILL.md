---
name: generate-music-video
description: >-
  Generate a short music video (MV). Propose before approval and spend;
  pending music may be planned, not executed. Not single-shot clips, UI tours,
  footage edits, exact lyric/beat/lip sync, seamless loops or full songs.
version: 1.3.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: hands
    hands: video-creator
    cost: metered
    output: "proposal-v<N>.md + SHA-256; approved: mv_<slug>_v<N>.mp4 + poster/review/raw/prompt.txt/qa.md"
    form:
      subject:
        required: true
        label: "lead subject; preserve identity"
      character_reference:
        required: false
        type: image
        label: "appearance image; upload consent"
      theme:
        required: true
        options: [theater, night-city, dream-garden, graphic-space]
        other: true
        references: references/themes/*.md
        label: "world; overridable defaults"
      theme_detail:
        required: false
        label: "motif/palette/material/light overrides"
      style:
        required: true
        options: [anime-3d, anime-2d, live-action, mixed-media]
        other: true
        references: references/styles/*.md
        label: "rendering medium; custom OK"
      performance:
        required: false
        label: "action; absent: propose, not idle"
      direction:
        required: false
        options: [performance, typographic, montage]
        other: true
        references: references/direction/*.md
        label: "staging; default performance; mixes OK"
      pace:
        required: false
        options: [relaxed, steady, snappy, intense]
        other: true
        references: references/pace/*.md
        label: "rhythm; new default steady; mixes OK"
      transition:
        required: false
        options: [continuous, cut, match-cut, whip, dissolve]
        other: true
        references: references/transition/*.md
        label: "shot boundary; new default cut"
      reference_video:
        required: false
        type: file
        label: "local sampled example; never uploaded"
      reference_focus:
        required: false
        label: "borrow camera/pace/world/type"
      music_mode:
        required: true
        options: [generated, supplied, silent]
        label: "native audio / master to finish / silent"
      music:
        required: false
        label: "sound/mood, not song copying"
      music_file:
        required: false
        type: file
        label: "finished local audio; required before generation"
      music_plan:
        required: false
        type: text
        label: "pending supplied music: owner/spec/order; proposal only"
      words:
        required: false
        label: "words; exact text deferred"
      must_keep:
        required: false
        label: "mandatory; finish or stop"
      aspect:
        required: false
        options: ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"]
        label: "default 16:9; check backend"
      duration:
        required: false
        type: int
        label: "5-15s; default reference 10, else 15"
      upload_inputs:
        required: false
        options: ["yes", "no"]
        label: "character-image upload consent"
      remote_analysis:
        required: true
        options: ["yes", "no"]
        label: "separate output video/audio upload consent"
      approved_plan:
        required: false
        type: file
        label: "Creator-approved proposal; absent: stop"
      approval_sha256:
        required: false
        label: "proposal hash; required with plan"
      slug:
        required: false
        label: "safe ASCII output stem, default mv"
      note:
        required: false
        type: text
---

<Procedure>

Uses video_generate, not a new API. Characters are inputs, not separate skills.
The skill name/path is now generate-music-video / generate/music-video, not an
output-filename or runtime-job-path rename: keep mv_<slug> stems and existing
artifact paths. There is no generate-mv alias leaf. Reissue active legacy jobs
under generate-music-video with a new proposal and new client approval; never
edit frozen old jobs, prompts or approvals, and preserve consumed attempts.

Form details: character_reference is one local appearance image, not a starting
frame. reference_focus selects camera, pacing, world or typography to borrow,
never an assumption that the example's subject should be copied. music describes
sound/mood, not an uploaded audio reference or a promise to reproduce a named
song. words are approximate generated lettering unless must_keep requires exact
text, deferred to separately approved finishing. must_keep includes identity,
wording, timing and other non-negotiable requirements; unsupported requirements
need an explicit finishing plan or a stop. Silent mode is intentionally silent;
supplied mode preserves music_file locally for separate approved assembly.
When music_file does not exist yet, music_plan describes the intended music,
its producing role, expected duration and the production/finishing order. It
is text, not a file path, audio, an upload grant or a generation approval.
Do not fabricate a WAV, future file hash or audio measurement to fill it.
upload_inputs authorizes the character reference leaving the machine for video
generation; a local path is not consent. remote_analysis is separate consent to
upload GENERATED video, including its audio, to the analysis provider; no means
temporal/audio QA remains unverified. Labels are compact for Hermes' 4000-character
discovery window; these details and the steps below remain part of the contract.

1. Use a work session even for the proposal. You own concrete MV direction
   within the filled form, not new client requirements. Inspect the existing
   video_generate schema/provider surface without calling it: duration, aspect,
   resolution, reference_image_urls for the character, and native audio for
   music_mode: generated (advertised audio support or an always-on native-audio
   capability). A prompt mentioning music is NOT proof of audio support.
   The current xAI-first chain does NOT advertise native audio; generated mode
   is presently a blocked request, not a selectable working feature. Offer
   silent/supplied only with explicit client agreement, or return the backend
   gap for the maintainer; do not silently switch sound mode or provider.
   xAI's reference-image path clamps duration to 10s although the schema says
   15s: check this mode-specific limit as well as the schema. Default request
   is 10s with character_reference, otherwise 15s, at 16:9 and 720p. Explicit
   >10s with an xAI character reference returns Q<n> before spend; never submit
   an impossible request and burn variants on its shortened result. Do not turn a
   reference into image_url: that changes appearance guidance into a starting
   frame. Never drop it or reduce the request to fit an unsupported backend.
    Round A may retain a local character_reference before upload consent: mark
    that consent pending and make no remote call. Before Round B, a
    character_reference without upload_inputs: yes returns Q<n> before any
    upload or generation; missing consent is not permission to omit the image.
   A named MiniMax request is not fulfilled merely by the xAI-first chain:
   unless the actual configured route can honor that model, return Q<n>.
   No provider/config changes, direct API scripts, or new external skills.
2. Load only the selected local references: styles from
   [anime-3d](references/styles/anime-3d.md),
   [anime-2d](references/styles/anime-2d.md),
   [live-action](references/styles/live-action.md),
   [mixed-media](references/styles/mixed-media.md); themes from
   [theater](references/themes/theater.md),
   [night-city](references/themes/night-city.md),
   [dream-garden](references/themes/dream-garden.md),
   [graphic-space](references/themes/graphic-space.md); directions from
   [performance](references/direction/performance.md),
   [typographic](references/direction/typographic.md),
    [montage](references/direction/montage.md); pace from
    [relaxed](references/pace/relaxed.md), [steady](references/pace/steady.md),
    [snappy](references/pace/snappy.md), [intense](references/pace/intense.md);
    transitions from [continuous](references/transition/continuous.md),
    [cut](references/transition/cut.md), [match-cut](references/transition/match-cut.md),
    [whip](references/transition/whip.md), [dissolve](references/transition/dissolve.md).
   These are authored recipes, not claims of proven model output. For a custom
   value, write an equally concrete block without coercing it to a listed one.
   Theme owns space/materials/light, style owns rendering, direction owns the
    emphasis. Pace controls action/camera accents, holds and edit rhythm;
    transition controls how approved shot boundaries connect, not their count.
    New proposals default to pace: steady and transition: cut; cut is used only
    if the proposal changes shots. A continuous performance is valid, including
    snappy motion without cuts. Explicit continuous plus a request for a cut
    montage needs clarification or a proposed resolution before approval.
    A slower performer with faster cuts is a valid described pace: preserve it.
    theme_detail and explicit client constraints override defaults;
   resolve conflicts before approval, never retain unwanted gold in an ice-blue
    theater. Do not build theme-by-style-by-subject skill combinations.
   For reference-led recreation, camera traversal, lens occlusion or foreground
   depth, also read [spatial direction](references/spatial-direction.md).
   Preserve the source-specific camera/object relationships before choosing
   defaults: a pupil dive or curtain wipe is not a generic hard cut. Separate
   observed evidence, the client's description and your proposed interpretation.
3. Round A (no approved_plan): no video_generate, video_analyze, image
   generation, TTS, audio generation or remote uploads. Inspect existing local
   inputs only. If local-only image inspection is unavailable, ask Creator for
   a description rather than calling remote vision without consent. For a
   reference_video, extract samples with the existing helper:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py frames <reference-video> <fresh-review-dir>
   ```

   Look at the sheet once, and at most two native frames; record sample times
   and findings before the next look. These samples suggest staging, not audio
   or exact rhythm. Never ask the client to reattach a readable local file.
   Never send the reference_video/music_file to video_generate or video_analyze.
   A path alone authorizes neither remote inspection nor generation uploads.
4. Write a new `<deliver>/proposal-v<N>.md`, choosing the next unused N even
   after a rejected proposal; never overwrite any previous proposal.
    Include the complete effective form with defaults, existing supplied input
    paths and SHA-256 hashes, the expanded theme (not just its name), subject/identity lock,
    rendering medium, intended performance, and a short progression from opening
    through development/highlight to ending. Include an explicit tempo section:
    subject-action accents, camera cadence, holds (including ending hold), shot
    rhythm when applicable, and transition method at intended boundaries. Write
    these into the actual prompt, not just the form. For snappy + cut, favor
    crisp actions and short visual accents over one long motion per 3-4s phrase;
    exclude long dissolves/ghosted overlaps and a prolonged final pose. Keep
    words sequential if requested, clearing the previous group before the next.
    Direction's four story phrases need not mean exactly four long shots.
    Approximate times are direction,
    not frame-accurate guarantees. Keep this detailed proposal separate from a
    compact UTF-8 `generation-prompt-v<N>.txt` containing ONLY the exact text
    to send. Do not concatenate reference documents or the full proposal.
    Distill subject/world/style once, short action/camera/word beats, then the
    essential pace/transition constraints; remove repetition and bookkeeping,
    not must_keep. For each critical spatial action, the proposal AND compact
    prompt retain START / CROSS / AFTER: camera position and opening/destination,
    the crossing's visible boundary, then what surrounds the camera after it.
    Name what must leave the screen and how subject scale changes. Choose the
    critical actions with Creator; do not silently drop one to satisfy length.
    The plan must distinguish showing an object from performing its action and
    specify the evidence needed. Measure the file with `wc -c <generation-prompt-vN.txt>`:
    require 1..1800 UTF-8 bytes INCLUDING its final newline before approval.
    This conservative shared-route budget stays below the observed FAL limit
    of 2048 UTF-8 bytes and xAI's reported 4096 limit (unit not confirmed).
    It is not a universal limit for all models. The tool schema has no length
    bound; schema compatibility alone missed this limit on the snappy trial.
    Record the exact prompt path, byte count and SHA-256 in the proposal. If it
    cannot fit while preserving required direction, stop for a scope decision.
    Include the actual compact generation prompt and the
   preflighted backend surface, requested duration/aspect/resolution/audio,
   consent decisions, planned variant/corrective allowance, and QA criteria.
   Separate generator freedom, must_keep, and deferred finishing explicitly.
   Exact lettering means a text-free generated base; exact beats/lip sync are
    unsupported, not promised by adding timestamps to the prompt. In Round A,
    supplied mode accepts either a real music_file or a nonblank music_plan.
    If neither is present, return Q<n> for the missing dependency description,
    not permission to generate music. An explicitly supplied but unreadable music_file is an
    input error, never silently replaced by music_plan. If only music_plan is
    present, write the complete direction proposal and compact prompt anyway,
    marked `status: pending-inputs` and `can_generate: false`. Record the
    missing music_file, its intended producer/spec/duration, the separate
    music approval/production step and the required finishing step. Its hash
    identifies a preliminary proposal, not an executable generation release.
    Pending character upload consent is also recorded as a missing permission;
    it does not prevent this zero-upload proposal. Do not ask the client to
    choose the creative concept again merely to resolve these dependencies.
    Supplied mode still yields a silent VISUAL MASTER, not a finished MV;
   include the separately released assembly dependency. If a required finish
   has no agreed available route, return blocked with that gap before spend.
   The client must approve any visual-master-only delivery explicitly.
   Compute `shasum -a 256 <proposal-vN.md>`, report its digest, and STOP. The budget
    is a ceiling, not approval. No approval fields means this stop on every run.
    A pending-inputs proposal is returned for dependency planning, not offered
    as a single approval that would start all production. Creator first obtains
    the separate music production release; this leaf never synthesizes it.
5. Round B requires BOTH approved_plan and approval_sha256 from Creator and
    `intent: revise <previous delivery>`. A pending-inputs proposal cannot enter
    Round B even when its hash matches. Supplied mode now requires the real,
    readable music_file and its hash; a music_plan alone never releases
    video_generate. When music or permissions arrive, return a NEW numbered
    proposal with those resolved inputs/consents and a new SHA-256 for client
    approval; never splice them into the old approved proposal or reuse its
    approval. Preserve the same work conversation and consumed-attempt ledger.
    Read the executable approved proposal, compare its
   digest, effective form, input hashes and grant with this request; only the
   approval fields and output bookkeeping may differ. Missing/mismatched
    approval, changed theme/pace/transition/words/inputs/consent or a materially different backend
    surface returns Q<n> or a new proposal, never a generation. Recheck the exact
    prompt-only file's hash and 1..1800-byte count immediately before calling.
    An old oversized approved prompt needs a new proposal/approval; do not
    silently shorten it, send it anyway, or regain a consumed attempt.
    Hash matching is
   an integrity check, not authentication; never manufacture Creator's approval.
   Inventory raw results/prompt/qa and in-flight work first. Never retry an
   unknown result or reset the grant on resume. An explicit revised allowance
    needs a new approval record; surviving attempts still count. An existing
    approved proposal without pace/transition keeps its frozen prompt and timing;
    do not inject new defaults or silently reinterpret it. To adopt tempo controls,
    return a new proposal for approval, preserving the consumed-call ledger.
6. Route preflight happens inside this session's tool context only: the
   video_generate schema/capabilities and the chain's advertised surface are
   the evidence. Never probe credentials from a terminal child or a venv
   script: terminal children do not inherit tool credentials, so such a probe
   reports a missing key for a route that works in the tool (2026-09-09: a
   job-local script returned a fal ValueError while FAL_KEY sat in the profile
   scope, and the job stopped at 0 calls). A chain such as vid-xai-fal is
   available when ANY member is; an unavailable or unverified secondary member
   is disclosed in the ledger, never a blocker, and never consumes an attempt.
   Stop before spend only when the member the approved surface needs (xAI for
   a character reference) is unavailable or the approved surface changed. A
   preflight finding records its stage and sanitized message, never only an
   exception type, and its outcome is either proceed within the approved grant
   or blocked with the named gap; "review required" is not an outcome, and an
   unverified route is never reported as a cleared budget check. A public
   per-second price is an assumption recorded in prompt.txt, not a verified
   bill or a cap: the grant is counted in attempts. Before the first call,
   write `<deliver>/prompt.txt` with approved proposal
   path/digest, exact prompt, effective parameters, input roles/consent, budget
   and attempt ledger. Japanese text travels via files/tool arguments, not
    shell argv. Read the approved prompt-only file as the prompt argument with
    no added preamble, notes or reference text; prompt.txt is the ledger, NOT
    the tool argument. A corrective prompt must also pass the byte check and
    retain the approved invariants before its allowed call. Call video_generate
    directly, not generate-clip (its one-shot,
   no-text, silent contract is different). ONE tool call produces one whole
   candidate, potentially multiple model-generated shots; do not split the
   proposal into separate paid shot calls. Pass prompt, approved duration,
   aspect_ratio and resolution; pass the single character image in
   reference_image_urls only when supported and upload_inputs: yes. Generated
   sound stays within this video call; no standalone music or TTS tool.
   Set audio only if advertised; an always-on native backend needs no invented
   toggle. For silent/supplied mode, request no music if possible, then remove
   any returned sound in finishing. Never claim MiniMax, a seed, a resolution
   or audio behavior that the tool did not actually return.
7. Default allowance is TWO variant attempts plus ONE corrective attempt total,
   including failures. Log an attempt before invoking the tool, then append
   its result/error. No automatic retry. An unknown outcome stops for status
   reconciliation rather than another paid call. Configured fallback can make
   several provider attempts per tool call: this allowance is NOT a dollar
   cap. Provider-specific requirements must be resolved before approval; no
   silently substituted images, sound modes or identity constraints.
8. Localize every returned file/URL immediately into a new `<deliver>/raw/`
   filename; preserve the raw result and provider provenance. Do not enable
   persistent public storage, overwrite an existing raw file, or deliver only
   an expiring URL. Use `curl --fail --location --retry 0 --output <new-path>`
   only after checking the target does not exist. Finish each local result:

   ```sh
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py edit <raw> <deliver>/mv_<slug>_v<N>.mp4
   python3 ${HERMES_SKILL_DIR}/../../scripts/clip-media.py frames <output> <deliver>/review-v<N>
   ```

   Add `--mute` ONLY for silent/supplied mode; preserve generated audio otherwise.
   Run commands separately; background/poll long encodes. Do not crop/upscale
   to hide a request mismatch. Copy review frame-01.png to a new poster path.
   No lettering, beat editing or supplied-music mux is hidden in this finish.
9. For each successful candidate: sheet once, native middle frame once, and
   only with remote_analysis: yes, video_analyze once on the WHOLE output.
   Ask for timecoded identity/performance/world/style errors, shot progression,
    must_keep violations, tempo/hold/boundary mismatches against the approved
    pace/transition, and audio presence/relationship when applicable.
   Above 30 MB use a scratch proxy via helper `edit --max-bytes 25000000`;
   do NOT mute a generated-audio proxy. Disclose proxy use. Append each finding
   to qa.md before the next visual call. Samples cannot verify continuity or
   music sync; model analysis is evidence, not a claim that a human listened.
   Declined/failed analysis leaves temporal/audio QA unverified; it is never
    itself grounds for another generation. Three global samples are not enough
    to judge a brief critical passage. When permitted local/native image review
    is available, inspect at most TWO critical windows per candidate, at most
    2 seconds and 24 frames per window, each with one sheet look and immediate
    qa.md append. Choose windows from the available timing evidence; if an event
    cannot be located, report missing evidence, not an expanding search loop.

    ```sh
    ffmpeg -hide_banner -loglevel error -n -ss <start-seconds> -i <output> -t <window-seconds> -vf "fps=12,scale=320:-1,tile=6x4" -frames:v 1 <new-window-sheet.png>
    ```

    Record source path, window start/duration and sample rate; a partial window
    may leave empty tiles, which are not source frames. Separate aperture shape
    fidelity from crossing evidence. A door pictured in the scene is not proof
    of passage, nor are blended frames or a successful decode. Keep whole-video
    continuity unverified without appropriate evidence; remote consent is unchanged.
10. If neither initial candidate passes and the defect is within approved
    generator freedom, use at most the one corrective attempt. Record the
    observed defect and prompt delta; do not change the approved subject,
    theme, pace, transition, words policy, audio mode, mandatory constraints or backend to fix it.
    A changed creative choice needs a new proposal and approval. Repeat the
    bounded QA, then stop regardless of outcome. Existing edit-clip may handle
    a separately released trim/format change; burned-in misspellings, broken
    faces or hands are not promised fixable in post. Never improvise a new
    editing skill or run Creator's legacy workflow yourself. If a critical
    spatial action fails in the full MV, report the gap rather than appending
    more adjectives and spending again. A separately granted single-shot
    generate-clip test can isolate that action; its success does not certify the
    integrated MV. No implicit shot-by-shot generation or assembly is authorized.

</Procedure>

<QA>

- Proposal dependencies: a supplied music_plan without music_file produces
  `pending-inputs`, never an executable approval. No invented file/hash, no
  audio generation and no upload in round A. A later real music_file or changed
  consent needs a new numbered proposal/hash; the old one remains untouched.
- Proposal: theme expanded into space/materials/light/staging, overrides kept,
  purposeful performance and readable progression, no hidden exact-text or
  beat-sync promise. Approval matches plan and inputs before any generation.
  Exact prompt-only file is 1..1800 UTF-8 bytes and matches its approved hash;
  length rejection is not repaired by an unapproved resubmission.
- Integrity: helper dimensions/codec/fps/duration/bytes/decoded; H.264/yuv420p
  MP4; requested duration within max(0.25s, one frame). Mismatched aspect or
  resolution is reported, not silently cropped/upscaled.
- Subject/world: identity and costume survive changing views; theme motifs,
  materials and light remain coherent; no accidental morphing or extra limbs.
  Named/custom style and direction cues are checked against the approved plan.
- Development: visible performance rather than a moving still; opening and
  highlight read, cuts/occlusions have purpose, ending is not an accidental
  truncation. Approximate timecoded model findings retain their uncertainty.
- Spatial actions: per critical event report START / CROSS / AFTER evidence
  with sample timestamps/paths, plus shape fidelity separately. Distinguish
  shown only, crossing evidenced, missing evidence and contradicted. A keyhole
  appearing without the rim passing out of frame and a sustained inside view
  is not a passing traversal. A successful isolated shot does not pass the same
  action in the full MV. Appealing motifs cannot cancel a failed must_keep action.
- Tempo/boundaries: action and camera accents, idle holds, ending hold and shot
  rhythm match the approved pace, not a generic minimum speed or cut count.
  Cut requests do not silently become dissolves; continuous requests do not
  gain shot breaks. Sequential words do not unintentionally overlap when the
  proposal forbids it. Fast edits must remain legible, not random flicker.
  Sampled stills cannot certify cut cadence or motion speed; preserve missing
  temporal evidence as UNVERIFIED. These are prompt directions, not guaranteed
  timestamps/BPM or permission to speed up the finished video globally.
- Words/audio: approximate generated lettering is labeled as such. Exact words
  deferred to finishing are NOT marked passed or complete. Generated mode must
  actually contain audio; silent/supplied masters must not. Supplied mode and
  any deferred exact text stay `needs finishing`, never a completed musical MV.
  No listening, exact lyric, beat or lip-sync claim from sampled frames.
- Spend/privacy: each attempt including failure is tallied; raw preserved;
  image upload and output-video analysis consent checked independently;
  reference video and supplied music never uploaded by this leaf. No-remote
  analysis means unverified temporal/audio quality, not an implicit pass.

</QA>

<Report>

Round A with missing music/consent: `generate-music-video / pending-inputs`;
proposal path/hash, `can_generate: false`, missing dependencies and next
separately approved music/permission steps. This is a completed preliminary
proposal, not a tool failure or a request to select the same concept again.
Do not present its hash as sufficient to start generation.

Executable Round A: `generate-music-video / awaiting approval` (or blocked); proposal path and
SHA-256; short expanded theme, beat proposal and tempo/boundary choices;
generator freedom/must_keep/
finishing split; backend limitations; continuation in the same work
conversation with `intent: revise <deliver>`, the full unchanged form,
`approved_plan: <path>` and `approval_sha256: <digest>`; planned allowance;
`spend: video_generate 0; video_analyze 0`. This is a proposal, not a movie.

Round B: proposal/digest, prompt/raw/output/poster/review/qa paths; per-candidate
technical facts and PASS/FAIL/UNVERIFIED findings; one recommendation if any;
`spend: video_generate <attempts>/<grant>; video_analyze <calls>` with known
provider/model and remaining grant. State `needs finishing` and its dependency
for a visual master, or the explicit silent/generated sound mode. Return
questions to Creator; never mark a failing/unverified candidate accepted.
Creator may relay a client's explicit acceptance of disclosed residual QA
gaps and close the job, but the evidence remains UNVERIFIED, never upgraded
to PASS. Pending mandatory finishing still prevents a completed-MV claim.

</Report>
