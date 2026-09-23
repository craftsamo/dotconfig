# Video hands (video-creator)

Ad, music-video, authoring references, tour, explainer-video and clip families. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Ad family

`ad` belongs to video-creator. The first release is `analyze-ad` and
`create-ad`; `generate-ad` and PV are planned, not advertised capabilities.
No legacy technic or mapping is retired. Both leaves use specialist
kind="work" even though media-generation cost is free.

An Ad addresses a specific audience with a promise and intended action. A
PV primarily introduces a subject's qualities, experience or world. Both
may contain a CTA, so neither CTA presence nor duration alone routes them.
Product categories stay form values, not separate ad skill families.

- `analyze-ad` reads one local <=60-second video for reference or review:
  measured metadata, timestamp-labeled overview, at most two dense windows
  and three native detail looks, then a timeline, visual construction,
  persuasion, issues and production handoff. Source claims are quoted as
  claims, not inherited client facts. Report observations, interpretations
  and unknowns separately; no provenance/model/conversion guessing. The
  helper uses clip-media's probe and only writes exclusive local evidence
  directories. Remote video analysis needs explicit yes and at most one call;
  image vision keeps the normal profile policy. No audio-stream-to-listening
  inference. Technical-only questions stay analyze-clip, even what_for: ad.
- `create-ad` authors a 6..30-second, 30fps HTML/CSS/GSAP ad from
  approved copy and local assets. Aspect selects 9:16 (1080x1920, default),
  16:9 (1920x1080), 1:1 (1080x1080), or 4:5 (1080x1350). Changing ratio
  means re-layout and a separately approved plan/source/preview, never a
  scaled or cropped old composition. Existing version-1 plans without
  aspect remain portrait; validation does not insert the new field or alter
  their hashes. Default office/bold-graphic/claim-led each
  has a concrete leaf-local reference; custom values override defaults.
  It does not generate media, synthesize speech, capture, or load external
  runtime skills. Client-finished PCM WAV and muted supplied MP4 are inputs.
  Raster product/logo files are validated; no SVG input in this first release.
- Content approval binds plan.json (exact copy/holds, supplied claims,
  complete asset hashes, proof samples). Preview approval binds the frozen
  source/checks/frames before final render. Creator relays both in the same
  work conversation; file hashes are integrity checks, not authentication.
  Local helper primitives come from tour; its existing contracts are not
  changed and no ad layout generator or generic render framework is added.
  Static copy checks do not prove visible text/reading time/claim truth.
  Final decode and visual evidence must retain temporal/listening gaps.

Verification is staged: helper/unit and real local render checks are distinct
from fresh specialist/client-path tests. Do not call direct fixture renders
client-live evidence. Reference video, output frames and jobs stay local and
untracked; never commit a downloaded reference ad or its commercial claims.
The initial local check used 30 overview frames, an 8-frame focused window
and one native detail of a supplied portrait ad, with no remote video call.
A clearly fictional text-only fixture passed real HyperFrames check/snapshot/
render and final full decode at 1080x1920, 30fps, 15 seconds; its three copy
holds were inspected. This proves the local path, not production art quality,
Japanese typography, listening or the two live client entry paths. Those
remain live acceptance work, not claims made by the helper tests. Runtime
identity is bound to preview approval; a changed CLI needs a new preview.
Aspect selection was checked with real local 15-second fixture renders at
all four native sizes, 30fps/H.264/yuv420p, full decode and sampled copy/CTA
inspection. The aspect-less plan/preview byte-preservation test passes. An
older scratch project's independent rescan was blocked by a Finder-created
.DS_Store under its frozen root, not by ratio validation; it was not deleted
or ignored to make the check pass. This does not relax frozen-source rules.

## Music-video family

`video-creator-pipeline/generate/music-video/` serves `generate-music-video`, not a collection of
character-mv/product-mv/character-loop combinations. Subject is a form input;
the distinct deliverable is a short MV-style progression with performance,
coherent world and highlights rather than clip's silent single shot. Existing
`video_generate` and `clip-media.py` remain the generation/finish path. No new
provider, API wrapper, gateway endpoint, TTS or external skill is introduced.

User shorthand "MV" routes to generate-music-video. This is a skill name/path
rename only: `mv_<slug>` output filenames, runtime job paths and historical
artifacts stay unchanged. No generate-mv alias leaf remains. Reissue active
legacy jobs under the new name with a new proposal and client approval,
preserving consumed attempts; never edit frozen old jobs or approvals. Historical
trial names below describe the leaf used at the time, not current routing.
The frontmatter closes within 3800 characters so upstream's 4000-character
discovery scan retains every form field, with room for future metadata.

- Style choices: anime-3d, anime-2d, live-action, mixed-media. Theme choices:
  theater, night-city, dream-garden, graphic-space. Direction choices:
  performance, typographic, montage. All accept free text. These are authored
  reference recipes, not live-render-certified presets. Only chosen references
  load; no menu/index generator or cross-media vocabulary service exists.
- A theme specifies space, materials, light, default colors and opportunities
  for staging. theme_detail/must_keep override those defaults. Theater includes
  both playing-card red/black/white and ice-blue/silver examples: a meaningful
  starting point, not an immutable look or fixed timeline. Style owns rendering;
  direction and tempo choices guide the approved proposal's staging and timing.
- Optional pace (relaxed/steady/snappy/intense) and transition
  (continuous/cut/match-cut/whip/dissolve) are local reference-backed fields,
  both open to free text. New proposals default steady + cut, where cut applies
  only at proposed shot changes, not a mandatory cut count. Snappy means crisp
  action/camera accents and short holds, including the ending; continuous can
  still be snappy without edits. Separate actor/camera/edit speeds may be
  described. Conflicting continuous/cut-montage instructions need resolution
  before approval. Prompt and QA carry these choices, not just the form.
  Tempo changes require renewed approval and never reset spent allowance.
  Existing approved plans without these fields keep their frozen timing/prompt.
  Exact cut timing/BPM is not guaranteed, and a global post-render speedup is
  not a substitute for the requested direction.
- Round A writes a new proposal-v<N>.md with the expanded world, identity lock, short
  beat progression, effective form/input hashes, actual prompt/backend limits,
  sound/finishing choices, consents and call allowance. It makes no media
  generation or remote-analysis calls. Creator shows the proposal to its human
  client through clarify or its assistant client through text. A budget alone
  never authorizes generation.
- Supplied music need not exist for Round A: a textual `music_plan` records
  the producer, specification, duration and music/finishing order. The proposal
  is `pending-inputs` with `can_generate: false`, not a generation release.
  Pending character-image upload consent likewise permits only local planning.
  Creator obtains the separate music production release, then supplies the
  real music_file and resolved consents for a NEW numbered proposal/hash and
  approval. Never mutate or execute the preliminary proposal, invent a WAV/hash,
  reset attempts or ask the client to reselect the already accepted direction.
- Round B continues the same specialist_call work conversation with the exact
  approved_plan path and approval_sha256, unchanged form and inputs. A mismatch
  or changed creative choice needs renewed approval. The digest binds content,
  not identity; this is an agent operating contract, not a tool-level payment
  authorization mechanism. Default 2 variants + 1 corrective counts every tool
  invocation including failures. Unknown results must be reconciled, never
  blindly retried, and the allowance does not reset on resume.
- Audio modes are generated (only when the actual backend advertises native
  audio; NOT advertised by the current xAI-first chain), supplied (silent visual master for separate approved assembly), or
  explicitly silent. A supplied track is not an audio reference sent to the
  model. Reference video stays local or becomes a client's written description;
  the current tool cannot consume reference video/audio. Character-image upload
  consent and generated-video remote-analysis consent remain separate.
- xAI silently caps reference-image requests to 10s even though its general
  capabilities say 15s. Default 10s with character_reference, otherwise 15s;
  reject an explicitly longer reference-mode request before spend. Never change
  the input's role to starting frame or drop it merely to bypass this limit.
- Exact text needs a text-free base and separately agreed finishing; exact
  lyric/beat/lip sync is not promised. No required finish with an unknown route
  may be hidden until after spend. A visual master is needs finishing, not a
  complete musical MV. A MiniMax mention does not reconfigure the xAI-first
  chain or justify pretending an actual output used that model.
- QA covers identity, world, performance/progression, text/audio policy,
  technical decode and budget evidence. Sampled frames do not establish full
  motion or sound quality. Declined/failed remote analysis stays UNVERIFIED;
  model audio findings are not a claim of human listening.

Implementation status: skill/routing and reference recipes added. An actual
assistant-shaped Creator CLI -> specialist_call(kind="work") -> VideoCreator
proposal round passed on 2026-09-07: versioned proposal and matching SHA-256,
expanded red/black/white theater with defaults overridden, four-beat direction,
no approval fields, and zero video_generate/video_analyze calls confirmed in
the session records. The work conversation remains idle awaiting a client
decision. Reference media was only probed/sampled locally, not visually
interpreted or uploaded; direction used the supplied textual description.
The subsequent user-approved silent trial made one video_generate call and no
retry/corrective/remote-analysis calls: xAI/grok-imagine-video returned a
15.041667s 1280x720/24fps result; raw audio was preserved in raw and removed
from the delivered H.264/yuv420p MP4. Full decode passed. Sampled primary-session
review found the requested theater/colors/cards and readable words, but a more
2D-anime appearance, less spatial camera staging and overlapping FLIP/BREAK
than the reference intended. This is one live trial, not recipe-wide quality
certification; temporal continuity remains unverified. Human-client live
handoff remains untested; the actual run used an assistant-shaped Creator CLI.
User feedback accepted the general direction but found action/cuts sluggish.
Version 1.1 adds the tempo controls above; snappy + cut is the proposed next
comparison, not an already-generated improvement. The previous 1-call grant
is exhausted; no additional generation is implied by updating the skill.
The user-authorized snappy/cut comparison then failed on input length: a
5158-byte local prompt (5157 after stripping) hit xAI's reported 4096 limit
and the reached FAL backend's 2048 UTF-8 byte limit. No video was returned;
the failed tool call consumed the second grant, with no resubmission and no
usage/cost returned. Version 1.1.1 separates the detailed direction proposal
from an exact prompt-only file, measured at 1..1800 UTF-8 bytes and hashed
before approval, then rechecked before submission. This is a conservative
limit for the observed chain, not a universal provider guarantee. New text
must be reapproved; failed attempts are never silently refunded or retried.
A subsequent proposal-only run through the same Creator/hands conversation
produced a compact 1683-byte prompt (including newline), independently measured
and hashed. Subject/world/style, snappy hard cuts, sequential lettering and
short ending were retained. No new generation or analysis call was made;
cumulative attempts remain 2/2 and the compact proposal awaits approval and
a new explicit grant. The user then approved that compact prompt and one
additional call: trial 3 succeeded via xAI/grok-imagine-video at 1280x720,
24fps, 15.041667s; silent finishing and full decode passed. Cumulative usage
is 3/3 including the failed length attempt, with no manual retries or remote
video analysis. Sampled comparison shows better sequential word separation,
but blended transition frames and a long-looking raised-card ending remain
despite snappy/cut instructions. This does not certify hard cuts, exact hold
duration or improved playback rhythm; no extra generation/edit was performed.
A user-requested original-recreation experiment then used one more call on
the same xAI text-to-video route, with a primary-authored 1778-byte prompt
grounded in 4fps reference samples rather than the stock theater outline.
Female character details, iris FALL, corridor, door/keyhole and ivory/gold
palette appeared, exposing omissions/conflicts in our earlier prompts. The
sampled result still showed blended transitions and depicted a keyhole without
the specified passage/vortex; object vocabulary did not guarantee camera/object
relationships. Cumulative calls are 4/4; no further retry ran. This is a single
stochastic compliance test, not a MiniMax-vs-Grok benchmark or proof of model
incapacity. Preserve source-specific spatial transitions before adding more
generic pace/style choices; the original's model/inputs/editing remain unknown.
Two further bounded tests used the same text-only Grok route: a 5s isolated
aperture passage (one call, generate-clip) and a 15s integrated MV (one call,
generate-mv). In sampled evidence the isolated camera crosses a growing rim
and continues inside the card/cloth tunnel, but the opening is a round peephole
above a small keyhole, not the intended contiguous keyhole. The integrated
version restores keyhole shape but substitutes blended scenic views for the
crossing/interior continuation; pupil entry is blended too. Cumulative calls
are 6/6, no retries. Unequal duration, narrative load and stochastic samples
prevent a causal model-capacity claim; isolated success is not an integration pass.
Version 1.2 makes source-specific START/CROSS/AFTER relations explicit in the
proposal and compact prompt through local references/spatial-direction.md,
with shape and passage graded separately. Two bounded local review windows
(<=2s,12fps each) may supplement global samples where consent allows; decode
does not prove continuity. Failed critical motion remains a quality gap even
when objects/styles match. Shot isolation or multi-shot production needs its
own release/allowance, never hidden expansion of one MV generation call.
This is additive: clip/tour and the broader legacy video families stay intact;
no legacy technic or assistant QA mapping retires on partial MV coverage.

## Video authoring references

The Three graphics option extends these three HyperFrames leaves with
optional graphics: three-webgl2, without a third explainer renderer or an
Assistant execution path. Local contract: video-creator-pipeline's
references/three-graphics.md. A dedicated pinned HyperFrames 0.8.35 / Three
0.185.1 / esbuild 0.28.2 / puppeteer-core 25.10.0 runtime avoids shared CLI
upgrade drift. Maintainer setup clones a dedicated browser and fixes software
ANGLE/SwiftShader. Source/hash checks precede vendor-only scan exemptions;
the adapter copy must match reviewed source. Jobs stage real assets, never
install, upgrade or change the GPU mode. Existing proposals and preview
approvals remain, with explicit v3/preview required for opted-in tours.

The renderer responds synchronously to HyperFrames time and supports procedural
Three geometry/materials and ShaderMaterial GLSL, not async loaders/addons or
history-dependent simulations. Separate forward/reverse/repeat layer audits
bind raw PNG hashes; actual HyperFrames errors are also checked. Encoded-video
sampling and native component crops remain necessary: raw-layer determinism
does not establish final UI appearance or continuous-motion quality. Synthetic
fixture commands under scripts/tests/fixtures/three-graphics are engineering
tests, not user approvals or an authorized advertisement.

`video-creator`'s `skills.external_dirs` includes four individual technical
directories — `hyperframes-core`, `hyperframes-animation`, `cut-the-curve`,
`oversized-cursor` — from the same harness-neutral `~/.agents/skills` store
described under "HyperFrames skills live outside the repo" in `AGENTS.md`.
These are the technical subset; the three knowledge-only craft pins are
described in [`overview.md`](./overview.md) "Media craft knowledge".
Only `create-tour`, `create-ad` and `create-explainer-video` may consult
them, per the shared rule in
`video-creator-pipeline/references/hyperframes.md`; every other leaf in this
profile (clip, MV, analyze-ad) does not use them, and Motion Canvas — one of
`create-explainer-video`'s two implemented renderer choices, selected
explicitly in its proposal and never a silent switch — is not part of this
pin: it needs no external HyperFrames skill and instead uses its own local
reference (`create/explainer-video/references/motion-canvas.md`). The four references are
optional, read-only, procedural background — staging/timing/determinism,
GSAP animation rules, specific in-scene staging techniques, and approved
pointer-led scenes — never a new approval gate, workflow or leaf, and never
a substitute for the leaf's own form fields, freeze/snapshot/render helpers
or Creator-relayed approvals, which stay exactly as documented under Tour
and Ad family below. `external_dirs` makes the four directories visible to
the whole profile at the config level; the procedural restriction to
create-tour/create-ad is enforced by each leaf's own Procedure, not by a
tool-permission sandbox. A missing, unreadable or ambiguous reference is
reported (one attempted lookup per needed resource) and the leaf uses local
authoring for that topic; that is not a blocker, and it is distinct from an
actual CLI/dependency failure or a failed approval/validation check, which
still blocks. A profile config change like this does
not restart a loaded resident session automatically — a fresh session picks
up the new `external_dirs` entries, an already-open one may not.

Verification (2026-09-08): `test_video_creator.py` exercises real Hermes
discovery/file serving in isolated stores, including missing skills/files
and ambiguous names. The scoped suite passed 283 tests and 18 subtests
(7 opt-in tests skipped); the all-profile assertion separately fails on
the unrelated assistant `storefront-reel-production` skill root. The
video-creator profile validator and both portable leaf validators pass
(Hermes metadata/name warnings remain). All four installed external skills
and selected reference files also loaded through isolated Hermes imports.
HyperFrames 0.8.30 rendered the existing 8-second overview-tour and 15-second
fictional-ad fixtures; full decode and representative frame review passed.
A fresh-context prose simulation covered six fallback/scope scenarios.
These are loader, contract and renderer checks, not live Creator-to-hands
consultation evidence. No gateway restart or live handoff was performed.

## Tour family

`video-creator-pipeline/create/tour/` serves `create-tour`, a new subject:
recreate from reference/design/text, edit supplied local footage, or capture an
explicitly approved sanitized Web demo for a <=60-second UI walkthrough.
Creator owns what_for/audience, semantic flow, fidelity and choice approvals;
VideoCreator authors task-local HTML/CSS/GSAP, state changes and camera/pointer.
No per-step screenshots or client-written steps JSON are required. Frame and
decorative background are separate from faithful product internals; simplified
UI is explicitly approved/labeled, never invented real-product functionality.
Intro/outro default ON (title-reveal/result-hold). The three references for each
are examples with other:true, not exhaustive presets. Custom directions remain
verbatim with concrete authored beats; only explicit none omits. Ambiguity goes
back as one clarification or proposed beat, never nearest-preset fallback.
Styles can also be authored locally beyond flat/glass/outline, without a registry.
Reference is inspiration/context, source is actual local footage, target is an
operation destination. None is capture consent. Omitted screen_mode preserves
recreate/v2 behavior; explicit recreate/supplied/capture uses v3 proposal approval.
Only VideoCreator's narrow capture.py wrapper operates sanitized Web demos under
approved scope. Native capture, login recording and privacy redaction are unavailable.
Narration consumes finished audio-creator WAV plus
current words.json; video-creator has no TTS or external runtime skills.

Creator routes this free leaf with `specialist_call(kind="work")`, never raw
A2A or a direct resident script. `authored.py` freezes v2/v3 source/contract/form,
checks real renders and publishes fresh preview/final evidence with full decode.
It does not generate layout or enumerate UI actions. The unchanged `tour.py`
direct entry remains usable for actual persisted v1 screenshot projects and
v1 scaffold calls; no migration or v2 interpretation of old forms is promised.
Only small IO/media primitives are shared, not the old composition engine.
GSAP core is vendored from npm 3.14.2 with hash/integrity provenance and its
own Standard No Charge license, not the skill's MIT license. Authoring is allowed
in task-local source, never managed scripts or frozen projects. Helpers are not
a sandbox for untrusted downloaded HTML; source must be reviewed before execution.
The portable skill-authoring validator's directory-name warning is intentional:
Hermes names nested leaves `<verb>-<subject>` (`create-tour` in `create/tour`),
with structured Hermes metadata and the established author/version fields.

Projects freeze source copies and hashes. Preview=yes authors/freezes/checks/
snapshots only; client approval resumes that unchanged project into a fresh
final directory. Changed fields need a new project/preview. Existing runtime
data, input files, deliveries and failed evidence are never deleted or
overwritten. Real render/decode and sampled contrast/layout evidence are
distinct from human task correctness, temporal quality and listening.

Verification belongs to `scripts/tests/test_tour.py` (v1) and
`scripts/tests/test_authored_tour.py` (v2); authored visual fixtures live under
`scripts/tests/fixtures/authored-tour/`. Synthetic render tests
are not earned product-live evidence; human-conversational and Assistant-
brief-shaped two-client handoffs remain pending until explicitly exercised.
Legacy v1 verification (2026-09-06, after independent review): 108 targeted tests plus 14 subtests
passed, including actual desktop/mobile MP4s, all decorative frame variants,
preview approval/tampering, text overflow and a timed synthetic WAV render.
HyperFrames 0.8.30 and ffmpeg 8.1.2 were exercised; sampled authored-text
contrast passed (desktop 12/12, mobile 11/11). English OCR ran locally;
Japanese language data was absent and its actionable failure was tested.
Timeline construction/registration is synchronous; only font-dependent
layout guards wait for fonts. Goal/first-step RGB hashes differ in both
previews and decoded MP4 frames, without requiring every step to differ.
OCR TSV preserves literal quotes and skips rows missing text. Tests default
to the system temp directory (TOUR_TEST_ROOT overrides it), clean ordinary
fixtures and intentionally retain only render-test evidence.
No gateway restart is needed for the on-disk implementation; loaded sessions
may retain their earlier contract. This subject does not retire or alter
creator-html-motion, legacy routes, clip/speech helpers or global 1:1 mappings.

Authored v2 verification (2026-09-07): the selected tour/clip/video-routing and
profile-validator suites passed 155 tests plus 18 subtests (3 opt-in legacy
render tests skipped). HyperFrames 0.8.30 rendered a 20-second illustrative
Light/Dark UI and 8-second overview, result-first, free-text and explicit-none
alternatives. All five have 13 distinct decoded sample hashes, full decode and
nonzero contrast audits. One contrast warning per video samples the hint hidden
behind the intentionally opaque modal; it is not a claim of zero findings.
Headless fixture checks cover selection, modal, partial/full typing, save,
four pointer contacts and reverse seeking. Browser pixel comparison records
hashes and permits only <=48 RGB channel differences of <=1/255 (observed
four one-unit pixels), never content or geometry drift. Main/alternate renders
are direct local evidence, not live Creator/hands sessions or real macOS actions.

Reproduce only with explicit local fixture-render approval and a new physical
scratch child (Pillow Python, installed HyperFrames/ffmpeg; no installs):

```sh
python scripts/tests/fixtures/authored-tour/example.py --root <fresh-absolute-child> --variant main --render
python scripts/tests/fixtures/authored-tour/audit.py <rendered-fixture-root>
node scripts/tests/fixtures/authored-tour/seek.mjs <installed-hyperframes-package.json> <headless-browser-binary> <rendered-fixture-root>
```

### Footage And Capture v3

The same leaf preserves frame/style/background/backdrop/free-text intro/outro.
Creator proposes semantic steps from goal/audience/start_state and optional flow;
clients need not write action scripts. An explicit mode first returns only
proposal-vN.md and SHA-256. The proposal's `tour` block binds the normalized form
and capture scope. Creator relays client approval in the same work conversation;
hashes bind bytes, not caller identity. Approved reconnaissance precedes approved
stateful recording. Changed scope needs a new proposal, not per-click approval
inside the existing scope. Exact preview approval remains a separate final gate.

`footage.py` fully decodes and trims local raw video at 1x, validates source
ranges, and records explicit keep/mute audio and source-to-timeline mapping.
Raw limits (300 s / 512 MB each, 1 GB selected inputs) are independent of final
<=60 s and prepared <=64 MB / bundle <=128 MB. `<video>` remains moving footage,
with unique id, muted/playsinline and framework-owned timing. Keep uses a separate
timed audio element. No screenshot replacement, fabricated event timings or
double cursor. Raw/source hashes, proposal and logs stay private, outside final.

`capture.py` runs installed agent-browser via the existing terminal surface.
It binds a private namespace/config/session to the job/proposal, holds an
exclusive flock, independently caps reconnaissance at four sessions and recording
at two takes per job (failures counted across proposal versions), checks origin/tab
state before/after actions, rejects arbitrary eval/navigation/login/upload and
unapproved selectors/data, and fsyncs pending action evidence before dispatch.
Recording replaces the context and leaves the old tab: only that verified owned
tab is closed, then page state and fresh snapshot are checked. Interruptions
retain raw/unknown actions; recovery closes only the owned session and cannot
replay an interrupted approval. SIGKILL cleanup relies on a private idle timeout
and explicit lease recovery, not a finally-block promise.
Unknown-selector discovery can use v1 recon, v2 recon plus an interrupted first
take, then v3 recon plus the reapproved second take. Recon under the exact current
proposal is still mandatory; no consent or evidence is relabeled/reused, and new
proposals cannot reset either budget or permit a third take.

Launch capture/recon/recovery using terminal background:true and notify:true from
the outset; save its terminal session_id and poll/wait only that process. A 180 s
scope can exceed the profile's 180 s foreground timeout after cleanup/validation,
so never retry a terminated foreground recording as a workaround. The browser
closes before probing/decoding; ordinary browser subprocesses are capped at 20 s
and the remaining <=180 s lease, stop/close at 20 s each, ffprobe at 180 s and
decode at 360 s. Validation subprocess work is <=540 s, the normal capture path
<=760 s plus bounded-size IO/scheduling. Background terminal timeout is not a
lifetime cap: supervise with bounded process waits and a 900 s operating cutoff,
then terminate only the owned terminal process and reconcile/recover its lease.
Do not replay interrupted approvals or launch a duplicate after a wait timeout.

This is a wrapper boundary, NOT a terminal/website sandbox. Existing terminal
access can bypass it; operating contracts forbid bypass. Agent-browser domain
filtering and post-action origin/tab checks do not guarantee arbitrary websites
are safe: GET/page scripts can mutate state, and popup/redirect loading can occur
before detection. Only approved controlled sanitized demos qualify. Source crops
are decorative, not verified privacy redaction. No new plugin/toolset or broad
browser/computer_use grant was added; cli/a2a retain terminal and existing scoped
registry rules. No global permission, dependency or gateway change is required
for the local wrapper.

Native proof gate: cua-driver 0.23.2 start_recording has only output_dir and
record_video; video captures the main display, not a scoped window. Existing
driver TCC grants were observed read-only, not changed or tested by capture.
Native remains blocked until continuous window-scoped capture AND a shared
desktop-action guard covering Assistant's existing computer_use are proven.
Never route around this through Assistant or full-desktop capture/cropping.

Local verification uses `scripts/tests/test_tour_footage.py` and
`scripts/tests/fixtures/captured-tour/`. The opt-in proof serves a dummy modal,
typing and scrolling UI only on loopback, records continuous WebM in an isolated
browser, trims it, and renders with HyperFrames 0.8.30. It is not a product-live
or two-client Hermes handoff. No durable client destination or model session is
selected automatically. Run with an existing physical scratch parent:

```sh
python scripts/tests/fixtures/captured-tour/proof.py --root <fresh-absolute-child> --render
node scripts/tests/fixtures/captured-tour/seek.mjs <installed-hyperframes-package.json> <headless-browser-binary> <project> <fresh-seek-output>
python scripts/tests/fixtures/captured-tour/audit.py --project <project> --final <final> --out <fresh-audit-output> --supplied-audio <fresh-audio-fixture>
```

Measured local v3 proof (2026-09-07): 10.2 s continuous WebM of a real loopback
dummy page, trimmed to 10.1 s and rendered into a 20 s 1280x720/30 fps H.264 MP4
with intro/outro. Full decode passed. Five source-time samples match forward and
reverse HyperFrames runtime seeks with identical screenshot hashes; decoded
source/final alignment is checked separately with explicit lossy pixel tolerances.
A separate supplied fixture adds a synthetic 440 Hz tone: keep produced nonzero
audio only in the footage window, with silent intro/outro. This is not a browser
audio-recording or subjective listening claim. Live local boundary tests exercised
password rejection, popup detection, redirect/GET side effects and SIGTERM with
retained raw evidence and blocked replay. Unit tests cover leases, recovery,
budgets, mode/approval integrity, media ranges and the unchanged legacy paths.
Primary-session safety review was followed by independent review, which found
two issues: the combined recon/take ceiling prevented the
documented second-take recovery flow, and capture lacked explicit background
execution/polling guidance. Both were addressed with separate budgets, a retry
provenance regression, background/recovery instructions and browser closure before
bounded media validation. Independent re-review confirmed both fixes and approved
the revised code within the documented limits. The follow-up targeted run
passed 137 tests plus 18 subtests (3 skipped); the full plugins/scripts run with
live local capture enabled passed 748 tests plus 64 subtests (4 skipped). Both
skill validators passed with only the existing untracked/Hermes-portability
warnings. A fresh real loopback acquisition, decode, preparation and freeze also
passed after the browser-close ordering change; that follow-up did not rerender
the already-proven MP4. Native capture remains
pending/blocked; review did not establish window-scoped recording or shared
desktop exclusion. Existing real probes demonstrated config/namespace/session
isolation arguments, record-start tab IDs and fresh-context behavior; they do not
prove isolation from every future agent-browser configuration surface.

Activation: the profile skill roots are already linked by install.sh, so new
children are visible through those directory links; verify links read-only.
Do not run the project-wide installer just to refresh this leaf. Loaded resident
sessions can retain old instructions; use a fresh approved work session for the
new contract. Gateway restart, native activation and real two-client handoff are
separate gates and were not performed. Rollback without rewriting data: route
new work to recreate, stop only owned capture sessions, preserve private evidence,
and resume old v1/v2 projects with their existing entry points. Do not delete or
downgrade existing v3 projects; render them with the version that created them.

Fixture variants are test cases only: `main`, `overview`, `result`, `custom`,
`none`. They are not production presets. The production helper has no such
dispatch. `reviewer-deep` reviewed the helper and its follow-up fixes; verifier
ran the scoped tests and both validators. Profile warnings are newly untracked
managed files until committed; portable skill warnings are the documented Hermes
metadata/nested-name exceptions. No gateway restart or live handoff was performed.

## Explainer-video family

`video-creator-pipeline/create/explainer-video/` serves `create-explainer-video`:
a bounded (1..180 second) local-authored explanation of a topic, for an
audience, toward a `learning_goal` — never a UI task walkthrough
(`create-tour`), an advertisement (`create-ad`), or a model-generated
music-video-style piece (`generate-music-video`). Always
`specialist_call(kind="work")`, even though the leaf is `cost: free`
(both renderers are local authoring — no provider fee). The renderer is
an explicit engine choice made in the proposal (plan `version`/`renderer`
fields) and preserved once made, never silently switched, including never
on failure: `renderer: hyperframes` (plan `version: 1`) authors HTML/CSS/
GSAP through the profile's existing local HyperFrames authoring; `renderer:
motion-canvas` (plan `version: 2`) authors a Motion Canvas `scene.tsx`
through the pinned local Motion Canvas runtime
(`engines/motion-canvas/`), maintainer-provisioned and never installed by a
job — see the leaf's own
`create/explainer-video/references/motion-canvas.md` for that engine's
source/plan/runtime contract, which needs no external HyperFrames skill.
Prefer Motion Canvas for reactive diagrams, algorithms and Canvas-based
explanation; prefer HyperFrames for HTML/UI or media-oriented
compositions. An old `version: 1` plan that named `renderer:
motion-canvas` before this engine existed was discussion-only and stays
non-executable — rendering with Motion Canvas always needs a fresh
`version: 2` proposal and a new approval, never reuse of that old hash.
Both engines support 16:9 (1280x720) or 9:16 (720x1280) at 30fps.

`framing` (none / bust / full) is a field independent of `performance`
(still / puppet / animated) and `lip_sync` (off / cues / baked). Bust
only *proposes* lip-sync cues as a default; that proposal is never a
silent substitute for an explicitly requested `off`. Full supports
whatever performance choice was actually approved — it is never an
automatic upgrade past what the client chose. Neither renderer gives this leaf automatic phoneme/viseme
inference, rig authoring, or native talking-model playback — generation
of a naturally talking video is explicitly not provided; the leaf never
claims to have produced one on its own. Two supported ways to still get a
performance: already-authored cue JSON plus mouth PNGs can drive a
deterministic mouth track, or a supplied finished muted MP4 that carries
its own sync evidence can carry a continuous animated performance. A
missing required performance asset is reported as `pending-inputs`, never
silently downgraded to a lesser framing/performance/lip_sync combination.

Character/asset resolution is Creator's job, not VideoCreator's: Creator
resolves the caller-selected workspace/asset root privately — a direct
path or an identity it already holds first, else a bounded name-only
lookup inside the caller's own known workspace, with an ambiguous
candidate returned as a question rather than a guess. No broad
home-directory scan is performed, and a missing file is never read as
license to invent a new character. Explicit assets are retained as
unchanged originals; the resolved asset root and any private asset name
stay working detail and are never embedded in a public proposal, form,
or report. An unspecified character in the brief is not "no character" —
Creator clarifies none vs. an existing character vs. a new one before
filling the form. An existing character missing a pose this explanation
needs is a missing-only-pose generation request through the fitting
image-creator mascot leaf, preserving the character's approved anchor
identity, never a fresh character concept.

New character images route through image-creator's mascot family (never
a direct call from VideoCreator); script text routes through Writer's
current `write-script` family, never the retired writer technic and
never Creator composing the script itself; grounding facts route through
researcher as needed; narration/mixed audio routes through audio-creator.
VideoCreator cannot call any of those hands or peers directly — it
returns a dependency request to Creator, which releases it as its own
separately budgeted and approved unit, the same composite-request
discipline used for any other multi-form job (`build-creator`).

The runtime lifecycle mirrors Tour/Ad's proposal-then-approval
shape: `propose --spec SPEC --out <new proposal-vN dir>` writes
`plan.json` + `proposal.md` + an assets snapshot and returns
`pending-inputs` or `awaiting-approval` together with the proposal's
SHA-256; inputs still missing are described in `spec.pending`, never
invented as files or hashes. The input script and the exact on-screen
copy are approved inputs, and each unit explains its before/change/after
state plus its visual expectations. A formally ready proposal exists only
once the selected modes' required inputs are in hand and the renderer is
supported; explicitly silent/no-character modes need no audio/character
assets. The user approves it through Creator. Only a matching
`freeze --approved-plan <proposal.md> --approval-sha256 HASH --source
SOURCE --project NEW` releases the frozen project; `snapshot --project
PROJECT --out NEW` follows, and only a matching `render --project
PROJECT --approved-preview PREVIEW --approval-sha256 previewhash --out
NEW` releases the final video. Nothing here self-approves, and a frozen
project or delivered output is never rewritten in place. Client
confirmation stays conversational, exactly like every other hands leaf —
a hash binds bytes, never approver authority.

For a HyperFrames plan, the existing curated HyperFrames external
references and their read-only, discussion-scoped policy (see "Video
authoring references" above) cover this leaf alongside create-tour/
create-ad; a missing or unreadable reference is reported with a
documented local-authoring fallback, never a blocker, while an actual
runtime failure or a failed approval/validation check still blocks
exactly as it already did for those two leaves. A Motion Canvas plan
consults none of those four references — its own local
`references/motion-canvas.md` stands in their place, and a missing/
unreadable reference there is likewise reported with a local-authoring
fallback. No fixed private asset path or name is introduced by
this leaf, and no new registry, environment variable, or discovery
script backs its character/asset resolution — Creator's existing
Group-local `deliver:` conventions and the leaf's own local authoring
apply unchanged. This family is additive: existing generate-music-video,
create-ad/analyze-ad, create-tour and Mix routes are unchanged, and a
request for explicit legacy Manim or its mathematical/3D scope retains
`creator-manim-explainer`. An unsupported requested renderer remains a
capability finding, not an automatic switch to that legacy technic or
between HyperFrames and Motion Canvas.

Verification (2026-09-09): 668 video/Mix regression tests and 29 subtests
passed (7 opt-in tests skipped). All-profile topology/discovery validation
and the portable explainer validator passed; the latter retains the three
documented Hermes metadata/nested-name portability warnings. Real HyperFrames
0.8.31 renders covered no character, bust/puppet/cues, full/still and supplied
full/animated video, including both aspect ratios. The cue-at-zero variant
also rendered correctly. The repeatable `fixtures/explainer-video/seek.mjs`
checks fresh initial paint and forward/reverse boundary/interior mouth states;
ordinary tests additionally exercise adjacent cues with real vendored GSAP.
The generated track declares a function called by the scene, because HF
coalesces inline scripts after external files; each boundary writes each
mouth once to avoid reverse-seek ordering conflicts. Mix tests cover actual
master/receipt/caption staging and decoded peak limits. These synthetic tone,
manual-cue and test-video fixtures are technical evidence only, not real
speech/character quality or live Creator-to-hands handoff verification.
No private character inputs, runtime installs or gateway restart were used.
That verification predates Motion Canvas and covers HyperFrames only; it is
retained as historical evidence, not proof of the Motion Canvas engine
below.

Motion Canvas (2026-09-09 addition): a second renderer,
`engines/motion-canvas/` (bootstrap `browser.ts`, import-confined esbuild+
Puppeteer `render.mjs`, maintainer-only `setup.mjs`) plus the leaf's own
`scripts/motion_canvas.py` adapter and `references/motion-canvas.md`, is
now implemented and documented as a second explicit engine choice
alongside HyperFrames — see the plan/renderer paragraph above for the
version-1-vs-2 selection rule and the leaf's own reference for the full
`scene.tsx`/`scene.meta` source contract, `@explainer/runtime` bindings,
frame-grid/size bounds, and maintainer provisioning steps. This is trusted
authored code, not a hostile-JavaScript sandbox. Rendering uses a dedicated
browser clone and exports canvas PNGs without Vite/editor/HMR; only the
approved master WAV is muxed by FFmpeg. Reactive visual bindings use the
view's globalTime signal, not generator-thread-only useTime().

Motion Canvas verification (2026-09-09): the ordinary video/Mix suites passed
712 tests and 29 subtests (14 native/opt-in cases skipped). With the native
Motion Canvas gate enabled, all 51 tests passed, including Japanese copy,
both aspects, no character, bust/cues, full/puppet, supplied animated video,
frozen-preview PNG equality, import confinement and cancellation cleanup.
Separate Motion Canvas and HyperFrames fixtures also rendered; the MC
Japanese fixture reproduced all eight approved raw sample PNG hashes.
The final QA records each engine's actual contrast status: MC requires visual
contrast/readability review rather than claiming an automated pass. The
pinned runtime's npm audit reported zero vulnerabilities after fixing the
transitive XML parser version. All-profile and portable leaf validation
passed with the documented metadata warnings. These are synthetic technical
fixtures, not real speech/character quality or live A2A handoff proof. No
private character assets or gateway restart were used.

## Clip family

`video-creator-pipeline/<verb>/clip/` is the first video hands family:
one short shot, not a generic film-production workflow. The profile uses
the same main/auxiliary model settings as image-creator, keeps native image
vision, and has video generation/analysis but no TTS, image generation, or
outbound A2A. The profile's `skills.external_dirs` pins four curated
HyperFrames technical references reserved for `create-tour`/`create-ad`/`create-explainer-video`
(see "Video authoring references" above); clip does not consult them. Deterministic families
may call HyperFrames through their own scripts; no external menu/router
is pulled into this one.

- `generate-clip`: 1-15 seconds, silent MP4, requested 720p, text or one
  starting image and one appearance reference. Styles are cinematic,
  flat-animation, clay, pixel or described. Default: 2 variant attempts +
  1 corrective total; failures count. Pixel is an aesthetic, not a proven
  sprite grid. Exact model capabilities are checked before spending.
- `edit-clip`: trim/contain-or-cover/mute/encode one <=60-second segment.
  MP4/WebM use optional two-pass byte targeting and an actual cap check;
  GIF checks its cap without silently changing size/fps. GIF repeat is
  playback metadata, never proof of a seamless loop. Outputs are exclusive
  and fully decoded before publication. Odd exact dimensions are refused;
  an original odd-sized clip is padded up, not cropped down.
- `analyze-clip`: findings on one <=60-second clip, no new video; `deliver`
  may be omitted. Original-file metrics, bounded sample frames and optional
  one-call whole-clip analysis are separate evidence sources. Frame times
  in `frames.json` are seek positions, not exact decoded PTS.

`clip-media.py` is the shared stdlib/ffmpeg helper (`probe`, `frames`,
`edit`); tests cover real MP4/WebM/GIF, trim, audio, SAR/rotation, byte caps,
odd dimensions and preservation of existing paths. GIF trimming happens
before palette generation and palette buffering is bounded. `free` means
zero media-generation calls, not zero reasoning/analysis cost. Uploading
an input image (`upload_inputs`) and remote video analysis
(`remote_analysis`) need separate consent. No means local sampled review
with temporal/audio quality unverified. Large authorized movies get a
proxy BEFORE the single analysis call; the ~50 MB limit is on base64.
The profile disables xAI persistent public storage; localize temporary
URLs immediately. No create-clip/source-clip leaf is invented: authored
motion and licensed stock sourcing are separate future families.

Live checks (2026-09-06): hands CLI edited a synthetic test pattern to
160x90, one second, silent H.264; local-only analysis respected no-upload
and reported temporal checks unverified; missing generation inputs stopped
with Q1/Q2 and zero generation. One generated clay-ball shot returned
1280x720, 24 fps, 3.041667 s. QA caught opening-frame clipping instead of
accepting it. The first analysis exposed an upstream-deleted
`_download_video` import; the MiMo plugin now calls `_download_media` and
has real-import handler tests. Analysis of the SAME shot then succeeded
and corroborated the framing defect, with no new generation. The initial
shot used the upstream persistent-storage default before it was disabled;
that pre-existing hosted artifact is not deleted by this config change.

Creator natural-language and Assistant-shaped CLI briefs both reached
video-creator through A2A with matching source/destination/fit/trim/mute/
format/slug fields (job directory and note differed), and produced matching
160x90/1 s/9378-byte outputs. Initial runs exposed two workflow limits:
loopback A2A carries an IP, not a verified profile name (a verbal origin
confirmation proves nothing); supplemental inline pixel scripts can hit
approval timeouts. The contract now states the transport limitation and
keeps edit QA to the existing helper plus bounded vision checks. Native
Telegram interaction and prolonged soak remain separate verification.
After that correction, fresh natural-language and Assistant-shaped runs
each completed with ONE A2A handoff (97 s and 92 s respectively), no
origin-confirmation round or supplemental approval block. Both outputs
are byte-identical to the direct hands CLI edit (SHA-256 verified).
The caller-owned resident wrapper was also exercised with missing
generation fields and a zero-call budget: it returned Q1/Q2, recorded the
video-creator session in Creator's registry, and was closed after the test.

Migration/rollback: keep `creator-generated-video` and its assistant
plan/QA mapping for explicitly requested legacy coverage, notably local
ComfyUI. That clip migration retired no other video/audio technic or card;
the subsequent speech retirement is described above. A failed served clip is a finding, never a
silent fallback. To withdraw the new route, remove the video-creator peer,
external skill root and served-clip routing plus the multiplex allowlist
entry, then restart the single gateway; leave artifacts and session state
intact. The pre-change tracked state is commit `47f9374`; do not reset a
working tree over other changes. Prior ignored learned content is retained
(the menu-era video-render-environment skill is disabled), and bundled
hermes-agent residue is retained as `SKILL.upstream.md`, not an active leaf.
