# Video hands (video-creator)

Ad, music-video, authoring references, tour, explainer-video, promotion, story, master and clip families. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`video-creator` receives filled forms on loopback A2A `:9908` (receive-only).
It has video generation/analysis but no TTS, no image generation and no
outbound A2A; it cannot call other hands or peers and returns dependency
requests to Creator instead. Shared contract: [`overview.md`](./overview.md).

## Ad family

`ad` belongs to video-creator. The first release is `analyze-ad` and
`create-ad`. A generated ad is not a leaf: its picture is text-free
generate-clip shots, composed by create-ad as supplied muted footage with
the exact copy, claims, product/logo rasters and CTA; generated footage
never stands in for the product. A PV authored from supplied material is
create-promotion ("Promotion family").
No legacy technic or mapping is retired. Both leaves always use specialist
`kind="work"` even though media-generation cost is free.

An Ad is an audience/promise/action deliverable, not a product-category skill
tree: it addresses a specific audience with a promise and intended action. A
PV primarily introduces a subject's qualities, experience or world. Both
may contain a CTA, so neither CTA presence nor duration alone routes them.
Product categories stay form values, not separate ad skill families.

- `analyze-ad` reads one local <=60-second video for reference or review:
  measured metadata, timestamp-labeled bounded overview, at most two dense
  windows and three native detail looks, then a timeline, visual construction,
  persuasion, issues and production handoff. Source claims are quoted as
  claims, not inherited client facts. Report observations, interpretations
  and unknowns separately; no provenance/model/conversion guessing. For a
  readable local video path, use frame extraction; never ask for a chat
  attachment instead. The helper uses clip-media's probe and only writes
  exclusive local evidence directories. Remote video analysis needs separate
  explicit consent and runs at most once; image vision follows the normal
  profile policy, with no promise of offline inference. No
  audio-stream-to-listening inference. Analyze may keep its report/evidence at
  an explicit deliver path but never produces a new ad. Technical-only
  questions stay `analyze-clip`, even with `what_for: ad`.
- `create-ad` authors a 6..30-second, 30fps HTML/CSS/GSAP ad from
  approved copy and supplied local assets. Aspect selects 9:16 (1080x1920,
  default), 16:9 (1920x1080), 1:1 (1080x1080) or 4:5 (1080x1350); canonical
  sizes live in `ad-render.py`, and source, preview and output must match.
  Changing ratio means re-layout and separately approved plan/source/preview,
  never a scaled or cropped old composition or reuse of an old preview.
  Existing version-1 plans without aspect remain portrait; validation does not
  insert the new field or alter their bytes and hashes. Default
  office/bold-graphic/claim-led each has a concrete leaf-local reference;
  custom values override defaults, and theme defaults never authorize
  generating missing assets. It does not generate media, synthesize speech,
  capture, load external runtime workflows, invent metrics or make client-live
  claims. Client-finished PCM WAV and muted supplied MP4 are inputs. Raster
  product/logo files are validated; no SVG input in this release.
- Content approval binds `plan.json` (exact copy/holds, supplied claims,
  complete asset hashes, proof samples). Preview approval binds the frozen
  source/checks/frames before final render. Create requires exact content-plan
  approval, then exact frozen-preview approval, both relayed by Creator in the
  same work conversation; the helper binds bytes, not approver identity.
  Runtime identity is bound to preview approval; a changed CLI needs a new
  preview. Local helper primitives come from tour; its existing contracts are
  not changed and no ad layout generator or generic render framework is added.
  Static copy checks are neither visual readability nor claim verification.
  Final decode and visual evidence must retain temporal/listening gaps.
- Audio: `create-ad` accepts up to 16 distinct finished WAV cues (SFX, music
  or speech), one placement per source, with distinct positive
  `data-track-index` values when there are several; unity gain and
  framework-owned timing stay, and the final decoded multi-audio true peak is
  measured (silent/undecodable/clipping output is rejected, never normalized;
  missing integrated LUFS is a warning). Existing single-audio plans and
  frozen hashes are not migrated. A mixed soundtrack uses
  `audio_workflow: mix` ([`audio.md`](./audio.md) "Mix family").

**Study purpose.** `create-ad` also owns a narrow diagnostic purpose, explicit
`purpose: study`: 1..10 s, a concrete question and real copy/message, no CTA and
no Mix mode. Its separately approved plan uses `freeze-study`; the ordinary
snapshot approval then releases `render-study`, kept separate from the final
commands. The frozen purpose is bound into plan/preview hashes and cannot run
through final render; ordinary ad validation never accepts a study. Output is
`study.mp4` with `final_eligible=false`, never an ad delivery. Both real
approval rounds and existing allowances remain; final-ad schemas/bytes and the
6..30 s/CTA requirements are unchanged. Other subjects keep their own supported
representative units and inherit no study flag or extra attempts.

Both purposes have a read-only `preflight --plan --assets` that checks actual
file suffix, path, size, hash and vendor compatibility before source authoring,
without executing source or producing output; passing it proves neither source
compatibility nor a visual result. `AD_STUDY_SMOKE_DIR=<new path>` opts into the
real synthetic renderer fixture; it proves plumbing only, not artistic quality,
continuous viewing or client acceptance.

Verification is staged: helper/unit and real local render checks are distinct
from fresh specialist/client-path tests; never call direct fixture renders
client-live evidence. Reference video, output frames and jobs stay local and
untracked; never commit a downloaded reference ad or its commercial claims.
Never delete or ignore a stray file (e.g. a Finder `.DS_Store`) under a frozen
root to make a rescan pass.

## Music-video family

`video-creator-pipeline/generate/music-video/` serves `generate-music-video`.
MV is a deliverable, not a collection of character/format skill products
(character-mv, product-mv, character-loop). Subject is a form input; the
deliverable is a short MV-style progression with performance, coherent world
and highlights rather than clip's silent single shot. Existing
`video_generate` and `clip-media.py` remain the generation/finish path, with
local style/theme/direction references. No new provider, API wrapper, gateway
endpoint, TTS or external skill is introduced; never introduce a menu generator
or cross-media presets.

User shorthand "MV" routes to `generate-music-video`. Only the skill name/path
was renamed: `mv_<slug>` output filenames, runtime job paths and historical
artifacts stay unchanged, and there is no old-name alias. Reissue active legacy
jobs under the new name with a new proposal and client approval, preserving
consumed attempts; never edit frozen old jobs or approvals. The closing front
matter stays within 3,800 characters so upstream's 4,000-character discovery
scan keeps every form field.

- Style choices: anime-3d, anime-2d, painted-anime, picture-book,
  live-action, mixed-media. Theme choices: theater, night-city, dream-garden,
  graphic-space. Direction choices: performance, typographic, montage,
  opening (an animated-series opening: world, cast glimpses, a text-free key
  visual). All accept free text. These are authored reference recipes, not
  yet validated with a paid render and not live-render-certified presets.
  Only chosen references load. Looks are described by traits, never by a
  studio, director or artist name — that goes into neither options nor
  prompts.
- A theme specifies concrete world vocabulary: space, materials, light, default
  colors and staging opportunities. `theme_detail`/`must_keep` override those
  defaults. A theme is a starting point, not an immutable look or fixed
  timeline. Style owns rendering; direction and tempo guide the approved
  proposal's staging and timing.
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
- Spatial direction: source-specific START/CROSS/AFTER relations are explicit
  in the proposal and compact prompt through `references/spatial-direction.md`,
  with shape and passage graded separately. Preserve source-specific spatial
  transitions before adding generic pace/style choices; object vocabulary does
  not guarantee camera/object relationships. Failed critical motion remains a
  quality gap even when objects/styles match.
- Round A writes a new `proposal-v<N>.md` with the expanded world, identity
  lock, short beat progression, effective form/input hashes, actual
  prompt/backend limits, sound/finishing choices, consents and call allowance,
  and returns only that file and its SHA-256 — zero media generation or
  remote-analysis calls. Creator shows the proposal to its human client through
  `clarify` or its agent client through text. A budget alone never authorizes
  generation.
- The exact prompt is a separate prompt-only file, 1..1800 UTF-8 bytes, measured
  and hashed before approval and rechecked before submission — a conservative
  limit for the current chain, not a universal provider guarantee. Changed
  prompt text must be reapproved; failed attempts are never silently refunded
  or retried.
- Supplied music need not exist for Round A: a textual `music_plan` records
  the producer, specification, duration and music/finishing order. The proposal
  is `pending-inputs` with `can_generate: false`, not a generation release.
  Pending character-image upload consent likewise permits only local planning.
  Creator obtains the separate music production release (music is never
  produced in this leaf), then supplies the real `music_file` and resolved
  consents for a NEW numbered proposal/hash and approval; a preliminary
  approval is not executable. Never mutate or execute the preliminary
  proposal, invent a WAV/hash, reset attempts or ask the client to reselect the
  already accepted direction.
- Round B continues the same `specialist_call` work conversation with the exact
  `approved_plan` path and `approval_sha256`, unchanged form and inputs. Only
  that match releases generation. A mismatch, changed input or changed creative
  choice needs a new proposal and renewed approval. The digest binds content,
  not identity; this is an agent operating contract, not cryptographic caller
  or payment authorization. Default 2 variants + 1 corrective counts every tool
  invocation including failures. Unknown results must be reconciled, never
  blindly retried, and the allowance never resets on resume.
- Audio modes are generated (only when the actual backend advertises native
  audio — the current xAI-first chain does not, so generated sound is blocked
  until a capable route is explicitly configured, never guessed), supplied
  (silent visual master for separately approved assembly), or explicitly
  silent. This leaf never uploads reference videos or supplied music; a
  supplied track is not an audio reference sent to the model. Reference video
  stays local or becomes a client's written description. Character-image
  upload consent and generated-video remote-analysis consent remain separate.
- xAI's reference-image path silently clamps to 10 s even though its general
  capabilities say 15 s. Default 10 s with `character_reference`, otherwise
  15 s; block an explicitly longer reference-mode request before spend. Never
  change the input's role to starting frame or drop it merely to bypass this.
- Exact text needs a text-free base and separately agreed finishing; exact
  lyric/beat/lip sync is not promised. No required finish with an unknown route
  may be hidden until after spend. A silent visual master needs finishing and
  is not a completed musical MV. A MiniMax mention does not reconfigure the
  xAI-first chain or justify pretending an actual output used that model.
- QA covers identity, world, performance/progression, text/audio policy,
  technical decode and budget evidence, with unverified temporal/audio QA kept
  explicit. Sampled frames do not establish full motion or sound quality; two
  bounded local review windows (<=2 s, 12 fps each) may supplement global
  samples where consent allows, and decode does not prove continuity.
  Declined/failed remote analysis stays UNVERIFIED; model audio findings are
  not a claim of human listening.
- Shot isolation or multi-shot production needs its own release/allowance,
  never a hidden expansion of one MV generation call.

This family is additive: clip/tour and the broader legacy video families stay
available, and no legacy technic or assistant QA mapping retires on partial MV
coverage.

## Video authoring references

`video-creator`'s `skills.external_dirs` pins four individual technical
directories — `hyperframes-core`, `hyperframes-animation`, `cut-the-curve`,
`oversized-cursor` — from the harness-neutral, CLI-owned `~/.agents/skills`
store (never the whole store; store maintenance rules: [`AGENTS.md`](../../AGENTS.md)). These are
the technical subset; the knowledge-only craft pins are separate
([`overview.md`](./overview.md) "Media craft knowledge") and do not widen this
subset's scope. Only `create-tour`, `create-ad`, `create-promotion`,
`create-story` and the HyperFrames path of `create-explainer-video` may
consult them, per the shared rule in
`video-creator-pipeline/references/hyperframes.md`; clip, MV and analyze-ad do
not, and Motion Canvas uses only its own local reference.

The four references are optional, read-only, procedural background —
staging/timing/determinism, GSAP animation rules, in-scene staging techniques
and approved pointer-led scenes — never a new approval gate, workflow or leaf,
and never a substitute for the leaf's own form fields, freeze/snapshot/render
helpers or Creator-relayed approvals. `external_dirs` makes them visible to the
whole profile; the restriction to those leaves is enforced by each leaf's
Procedure, not by a tool-permission sandbox. A missing, unreadable or ambiguous
reference is reported (one attempted lookup per needed resource) and the leaf
uses local authoring for that topic — not a blocker and not a runtime failure —
while an actual CLI/dependency failure or failed approval/validation check
still blocks. A config change is picked up by a fresh session; an already-open
resident session may not see new `external_dirs` entries.

**Motion vocabulary.** Separately from those external pins, the kernel's own
`references/motion-vocabulary.md` is read by all five authored leaves —
create-promotion, create-story, create-ad, create-tour and create-explainer-video (both
renderers; Motion Canvas uses names and looks only) — before the plan that
fixes their beats, and they name its entries instead of generic "fade",
"slide" or "card". It is a dictionary of names, looks and usual builds for
text animations, transitions, camera, effects, components, compositions and
visual metaphors (an abstract idea carried by a physical image, such as a
bottleneck as a funnel). It adds no plan field, schema or rule; why it stays
rule-free: "Storyboard vocabulary" under the Promotion family.

**Three graphics** is an opt-in (`graphics: three-webgl2`) on create-tour,
create-ad and the HyperFrames path of create-explainer-video — not a third
explainer renderer, an Assistant runtime or a new video subject. It selects one
synchronous WebGL2 canvas with core procedural Three.js geometry/materials and
custom `ShaderMaterial` GLSL under the same paused GSAP clock; local contract:
`video-creator-pipeline/references/three-graphics.md`. The engine pins its own
HyperFrames, Three, esbuild, puppeteer-core (locked in `engines/three-webgl/`)
and Node identity plus a dedicated
cloned browser with fixed software ANGLE/SwiftShader backend; never use or
downgrade the mutable global CLI for these jobs. `engines/three-webgl/setup.mjs
--browser <path>` is maintainer-only; jobs only stage verified real assets
through `three_graphics.py` and never install, upgrade or change the GPU mode.
Source/hash checks precede vendor-only scan exemptions, and the adapter copy
must match reviewed source.

Opted-in tours require an explicit `screen_mode`/v3 and an approved preview,
even when `preview=no`; old omitted-mode projects and existing proposals keep
their exact behavior. Preview binds runtime/layer evidence: forward, reverse
and repeat seeks and fresh-process layer PNGs must match by raw hash, and actual
render-log errors fail the job even when the CLI exits zero. Audit logs and
owned-browser cancellation stay observable. Pixel equality is not artistic
acceptance: inspect encoded motion and native UI crops. Not authorized: async
loaders, addons, WebGPU, history-dependent simulation, hardware fallback,
global install, or any change to prior frozen jobs. Synthetic fixtures under
`scripts/tests/fixtures/three-graphics` are engineering tests, not user
approvals or an authorized advertisement.

## Tour family

`video-creator-pipeline/create/tour/` serves `create-tour`: bounded (<=60 s)
task-local authored UI walkthroughs — recreate from reference/design/text, edit
supplied local footage, or capture an explicitly approved sanitized Web demo —
with frozen source projects, exclusive preview/final directories and a safe
approval resume. It is a new subject, not a global legacy retirement.
Creator owns what_for/audience, semantic flow, fidelity and choice approvals;
VideoCreator authors task-local HTML/CSS/GSAP, state changes and camera/pointer
from approved reference images, design and text. No per-step screenshots or
client-written steps JSON are required. Frame and decorative background are
separate from faithful product internals; simplified UI is explicitly
approved/labeled, never invented real-product functionality.

Intro/outro default ON (title-reveal/result-hold). The three references for each
are examples with `other: true`, not exhaustive presets. Free-text directions
stay verbatim with concrete authored beats; only an explicit "none" omits them.
Ambiguity goes back as one clarification or proposed beat, never a
nearest-preset fallback. Styles can be authored locally beyond
flat/glass/outline, without a registry.

Reference is inspiration/context, source is actual local footage, target is an
operation destination; they are distinct and none of them is consent.
`screen_mode` is recreate (omitted preserves v2 behavior), supplied or capture;
explicit modes use v3 proposal/hash approval without migrating frozen v1/v2
artifacts. Narration consumes finished audio-creator WAV plus current
`words.json`; Tour makes no edits to frozen source, external runtime
workflows/executables or TTS.

Creator always routes this free leaf with `specialist_call(kind="work")`, never
raw A2A or a direct resident script. `authored.py` freezes v2/v3
source/contract/form, checks real renders and publishes fresh preview/final
evidence with full decode; it never generates layout/UI or enumerates UI
actions. The unchanged `tour.py` entry remains for persisted v1 screenshot
projects and direct v1 scaffold calls; no migration or v2 interpretation of
old forms is promised. Only small IO/media primitives are shared, not the old
composition engine. GSAP core is minimally vendored with its own license
(Standard No Charge, not the skill's MIT license) and hash/integrity
provenance. Authoring happens in task-local source, never managed scripts or
frozen projects. Helpers are not a sandbox for untrusted downloaded HTML;
source must be reviewed before execution. The portable skill-authoring
validator's directory-name warning is intentional: Hermes names nested leaves
`<verb>-<subject>` (`create-tour` in `create/tour`).

Projects freeze source copies and hashes. Preview=yes authors/freezes/checks/
snapshots only; client approval resumes that unchanged project into a fresh
final directory. Changed fields need a new project/preview. Existing runtime
data, input files, deliveries and failed evidence are never deleted or
overwritten. Real render/decode and sampled contrast/layout evidence are
distinct from human task correctness, temporal quality and listening.

Verification: `scripts/tests/test_tour.py` (v1),
`scripts/tests/test_authored_tour.py` (v2) and
`scripts/tests/test_tour_footage.py` (v3); fixtures under
`scripts/tests/fixtures/{authored-tour,captured-tour}/`. Fixture variants
(`main`, `overview`, `result`, `custom`, `none`) are test cases only, not
production presets. Browser pixel comparison permits only <=48 RGB channel
differences of <=1/255, never content or geometry drift. Synthetic render tests
are not product-live evidence; the human-conversational and Assistant-brief
two-client handoffs remain pending until explicitly exercised. Reproduce only
with explicit local fixture-render approval, a fresh physical scratch child and
already-installed tools (no installs):

```sh
python scripts/tests/fixtures/authored-tour/example.py --root <fresh-absolute-child> --variant main --render
python scripts/tests/fixtures/authored-tour/audit.py <rendered-fixture-root>
node scripts/tests/fixtures/authored-tour/seek.mjs <installed-hyperframes-package.json> <headless-browser-binary> <rendered-fixture-root>
python scripts/tests/fixtures/captured-tour/proof.py --root <fresh-absolute-child> --render
node scripts/tests/fixtures/captured-tour/seek.mjs <installed-hyperframes-package.json> <headless-browser-binary> <project> <fresh-seek-output>
python scripts/tests/fixtures/captured-tour/audit.py --project <project> --final <final> --out <fresh-audit-output> --supplied-audio <fresh-audio-fixture>
```

Activation and rollback: profile skill roots are already linked, so new
children are visible; verify links read-only and do not run the project-wide
installer just to refresh this leaf. Loaded resident sessions can retain old
instructions; use a fresh approved work session. Gateway restart, native
activation and real two-client handoff are separate gates. Roll back without
rewriting data: route new work to recreate, stop only owned capture sessions,
preserve private evidence, resume old v1/v2 projects with their existing entry
points, and never delete or downgrade existing v3 projects — render them with
the version that created them.

### Footage And Capture v3

The same leaf preserves frame/style/background/backdrop/free-text intro/outro.
Creator proposes semantic steps from goal/audience/start_state and optional flow;
clients need not write action scripts. An explicit mode first returns only
`proposal-vN.md` and SHA-256. The proposal's `tour` block binds the normalized
form and capture scope. Creator relays client approval in the same work
conversation; hashes bind bytes, not caller identity. Approved reconnaissance
precedes approved stateful recording. Changed scope needs a new proposal, not
per-click approval inside the existing scope. Exact preview approval remains a
separate final gate.

`footage.py` fully decodes and trims local raw video at 1x, validates bounded
source ranges, and records explicit keep/mute audio and source-to-timeline
mapping. Raw limits (300 s / 512 MB each, 1 GB selected inputs) are independent
of final <=60 s and prepared <=64 MB / bundle <=128 MB. `<video>` remains moving
footage, with unique id, muted/playsinline and framework-owned timing. Keep uses
a separate timed audio element. No screenshot replacement, fabricated event
timings or double cursor. Raw/source hashes, proposal and logs stay private,
outside final.

`capture.py` owns isolated, sanitized Web recording and runs installed
agent-browser via the existing terminal surface. It binds a private
namespace/config/session to the job/proposal lease, holds an exclusive flock,
independently caps reconnaissance at four sessions and recording at two takes
per job (failures counted across proposal versions), checks origin/tab state
before/after actions, rejects arbitrary eval/navigation/login/upload and
unapproved selectors/data, and fsyncs pending action evidence before dispatch.
Recording replaces the context and leaves the old tab: only that verified owned
tab is closed, then page state and a fresh snapshot are checked. Interruptions
retain raw/unknown actions; recovery closes only the owned session and cannot
replay an interrupted approval. SIGKILL cleanup relies on a private idle timeout
and explicit lease recovery, not a finally-block promise. Unknown-selector
discovery can use v1 recon, v2 recon plus an interrupted first take, then v3
recon plus the reapproved second take. Recon under the exact current proposal
is still mandatory; no consent or evidence is relabeled/reused, and new
proposals cannot reset either budget or permit a third take.

Launch capture/recon/recovery with terminal `background: true` and
`notify: true` from the outset; save its terminal session_id and poll/wait only
that process. A 180 s scope can exceed the profile's 180 s foreground timeout
after cleanup/validation, so never retry a terminated foreground recording as a
workaround. The browser closes before probing/decoding; ordinary browser
subprocesses are capped at 20 s and the remaining <=180 s lease, stop/close at
20 s each, ffprobe at 180 s and decode at 360 s. Validation subprocess work is
<=540 s, the normal capture path <=760 s plus bounded-size IO/scheduling.
Background terminal timeout is not a lifetime cap: supervise with bounded
process waits and a 900 s operating cutoff, then terminate only the owned
terminal process and reconcile/recover its lease. Do not replay interrupted
approvals or launch a duplicate after a wait timeout.

This is a wrapper boundary, NOT a terminal/website sandbox. Existing terminal
access can bypass it; operating contracts forbid bypass. Agent-browser domain
filtering and post-action origin/tab checks do not make arbitrary websites
safe: GET/page scripts can mutate state, and popup/redirect loading can occur
before detection. Only approved controlled sanitized demos qualify; no
authenticated/private-region capture and no privacy redaction is claimed —
source crops are decorative. No new plugin/toolset or broad
browser/computer_use grant exists; cli/a2a retain terminal and existing scoped
registry rules.

Native capture is UNAVAILABLE: cua-driver's `start_recording` captures the main
display, not a scoped window, and no cross-profile desktop-action guard covers
Assistant's `computer_use`. It stays blocked until continuous window-scoped
capture AND a shared desktop-action guard are proven. Never grant
`computer_use` to VideoCreator, and never route around this through Assistant
or full-desktop capture/cropping.

## Explainer-video family

`video-creator-pipeline/create/explainer-video/` serves `create-explainer-video`:
a bounded (1..180 s) local-authored explanation of a topic, for an audience,
toward a `learning_goal` — never a UI walkthrough (`create-tour`), an ad
(`create-ad`), a model-generated MV (`generate-music-video`) or a
talking-model product. Always `specialist_call(kind="work")`, even though the
leaf is `cost: free`.

**Renderer.** The engine is an explicit choice made in the proposal and
preserved — never silently switched, including on failure. `renderer:
hyperframes` (plan `version: 1`) authors HTML/CSS/GSAP through the profile's
local HyperFrames authoring; `renderer: motion-canvas` (plan `version: 2`)
authors a Motion Canvas `scene.tsx` through the pinned local runtime in
`engines/motion-canvas/` with the leaf's `scripts/motion_canvas.py` adapter and
its own reference `create/explainer-video/references/motion-canvas.md` (source,
plan, runtime and provisioning contract), with no dependency on the external
HyperFrames skills. Prefer Motion Canvas for reactive diagrams, algorithms and
Canvas-based explanation; prefer HyperFrames for HTML/UI or media-oriented
compositions. Both render 16:9 (1280x720) or 9:16 (720x1280) at 30 fps. An old
`version: 1` plan naming `motion-canvas` was discussion-only and stays
non-executable: it needs a fresh `version: 2` proposal and new approval, never
a resume of the old hash. An unsupported requested renderer is a capability
finding, not an automatic switch between engines or to legacy
`creator-manim-explainer`, which a request for explicit Manim or its
mathematical/3D scope still retains.

**Performance fields.** `framing` (none / bust / full) is independent of
`performance` (still / puppet / animated) and `lip_sync` (off / cues / baked).
Bust only *proposes* lip-sync cues by default, never a silent substitute for an
explicit `off`. Full supports whatever performance the client actually approved,
never an automatic upgrade. Neither renderer provides phoneme/viseme inference,
rig authoring or native talking-model playback, so the leaf never generates a
naturally talking video on its own. Two supported routes: already-authored cue
JSON plus mouth PNGs drive a deterministic mouth track, or a supplied finished
muted MP4 carrying its own sync evidence carries a continuous animated
performance. A missing required performance asset is reported as
`pending-inputs`, never a silent downgrade of framing/performance/lip_sync.

**Characters and dependencies.** Creator, never VideoCreator, resolves the
caller-selected workspace/asset root: a direct path or an identity it already
holds first, else a bounded name-only lookup inside the caller's own known
workspace; an ambiguous match goes back as a question. Never do a broad
home-directory scan, and never invent a new character because a file is
missing. Explicit assets are kept as unchanged originals; the resolved root and
private asset names stay working detail and never enter a public proposal, form
or report. No fixed private asset path, registry, environment variable or
discovery script backs this; Creator's Group-local `deliver:` conventions
apply. An unspecified character is not "no character": Creator clarifies none
vs. existing vs. new. An existing character missing a needed pose becomes a
missing-only generation request through the fitting image-creator mascot leaf,
preserving its approved identity; new character art goes through
image-creator's mascot family. Script text goes through Writer's current
`write-script` family — never the retired writer technic and never Creator
composing the script itself; grounding facts go through researcher as needed;
narration/audio through audio-creator. VideoCreator returns a dependency request
to Creator, released as its own separately budgeted/approved unit.

**Lifecycle.** `propose --spec SPEC --out <new proposal-vN dir>` writes
`plan.json` + `proposal.md` + an assets snapshot and returns `pending-inputs`
or `awaiting-approval` with the proposal SHA-256; missing inputs are described
in `spec.pending`, never invented files or hashes. The approved script and exact
on-screen copy are settled inputs; each unit explains its before/change/after
and visual expectations. A proposal is formally ready only once the selected
modes' required inputs and a supported renderer are in hand; silent or
no-character modes need no audio/character assets. The user approves through
Creator. Only then do `freeze --approved-plan <proposal.md> --approval-sha256
HASH --source SOURCE --project NEW` and `snapshot --project PROJECT --out NEW`
run, and only a matching `render --project PROJECT --approved-preview PREVIEW
--approval-sha256 previewhash --out NEW` releases the final video. Nothing
self-approves; frozen projects and delivered outputs are never rewritten.
Client confirmation is conversational; hashes bind bytes, not approver
authority.

**References.** A HyperFrames plan uses the curated external references under
their read-only policy ("Video authoring references" above); a missing or
unreadable reference is reported with a local-authoring fallback, never a
blocker, while real runtime or approval errors still block. A Motion Canvas plan
uses only its own local reference (same fallback rule) and the pinned local
runtime.

**Motion Canvas runtime.** The maintainer provisions it explicitly with
`node hermes/engines/motion-canvas/setup.mjs --browser <browser>`; jobs never
install or upgrade it. Setup APFS-clones a supplied macOS `.app` browser into
ignored `runtime/browser/Renderer.app` (signed contents preserved, avoiding a
Dock/LaunchServices clash with the everyday browser) or uses a non-app
Chromium/headless-shell binary directly; it never copies cookies or a profile,
so every render gets a fresh isolated one. Rerunning setup against the same
pinned lock skips reinstalling but never overwrites a different existing clone
or a changed lock — that drift needs explicit maintainer replacement and a new
preview approval. Every preview records the actual runtime/Node/browser
identity; a normal browser version change doesn't by itself require
reinstalling, but any changed identity needs a fresh preview and approval.
Scenes are trusted authored code, not a hostile-JavaScript sandbox. Rendering
exports canvas PNGs without Vite/editor/HMR, and only the approved master WAV is
muxed by FFmpeg. Reactive visual bindings use the view's `globalTime` signal,
not generator-thread-only `useTime()`. On HyperFrames, the generated mouth track
declares a function the scene calls (HyperFrames coalesces inline scripts after
external files), and each cue boundary writes each mouth once to avoid
reverse-seek ordering conflicts.

Final QA always carries the engine's contrast-audit status; Motion Canvas has no
automated contrast check and reports "requires manual visual review". Synthetic
tone, manual-cue and test-video fixtures are technical evidence only, not real
speech/character quality or live Creator-to-hands handoff proof. The family is
additive: existing music-video, ad, tour and Mix routes are unchanged.

## Promotion family

`video-creator-pipeline/create/promotion/` serves `create-promotion`
(2026-09-23, renamed from `create-motion` the same day): authored promotion
video — launch/promo, brand or sizzle pieces, feature reveals, kinetic
typography, logo stings — 3..60 s at 30fps, 16:9 (default), 9:16, 1:1 or
4:5, that VideoCreator designs and draws itself in HTML/CSS/SVG/GSAP,
optionally matching a local reference video (`reference_use: inspiration |
reproduce`). Always `kind="work"`; free.

**Why it exists.** Before it, no served video leaf fit a launch/promo piece
(ad needs approved assets and a CTA, tour is a UI walkthrough, explainer a
learning goal), so Creator fell through to legacy `creator-html-motion` and
authored the video in its own broker context. The owner chose to move the
authoring into the hands (`~/Workspaces/.deliverables/creator-ab-2026-09/`).

**Structure approval, free look (v2).** The first version approved a
storyboard that fixed pixel sizes and allowed only "small execution fixes"
afterwards. In the blind re-measure (r11) the same three "too small, too
flat" gaps survived from the first review to the final render and the film
scored lowest of three (fidelity 3, taste 2, against 4/4 for Creator's own
authoring). v2 therefore approves structure only — beats, timing, verbatim
copy, seams, audio plan, the look in words — and makes the look an explicit
improve loop: every draft renders a `compare.png` (reference above, draft
below, at the same eight relative positions of each film), VideoCreator
writes the three biggest gaps against the reference and the leaf's
`<Standard>` (scale, depth, type, motion, density) and fixes them by
redesign, up to 8 drafts. The earlier
12-look reference cap is gone; the `vision-window` plugin still limits a step
to three images. In the same-session blind re-measure (2026-09-24) v2 (fidelity 4,
taste 3) tied the OpenCode baseline on pairwise preference and beat both v1 and
Creator's own authoring; cost 28 vision looks and ~17M input tokens per job.

**Storyboard vocabulary.** The storyboard decides the film's taste, not
the implementer: in a blind swap (2026-09-24,
`~/Workspaces/.deliverables/video-craft-ab-2026-09/`) the same storyboard
scored the same whether Hermes or OpenCode built it. Round A therefore
reads the kernel's `references/motion-vocabulary.md` — names of text
animations, transitions, camera moves, effects, components and compositions,
each with its look and usual build, and no rules — and names them in the
storyboard instead of generic "fade", "slide" or "card". With it, films
reached through the Assistant ranked first and second of eight. A rules
layer (numeric defaults, avoid-lists, self-scoring), a static-frame metrics
gate and a cross-family critic were tried in the same study and lowered or
did not move the ratings; keep them out.

**Lifecycle.** Round A writes `storyboard.md` and `promotion.py propose`
stores it as `proposal-vN/storyboard.md` with its SHA-256 and
`awaiting-approval` / `pending-inputs`. One Creator-relayed approval
releases authoring, drafts and the final. `promotion.py render --quality
final` verifies the hash, root canvas/duration, no remote references, strict
lint, then renders with the installed `hyperframes` CLI and checks canvas,
fps, duration (±0.1 s), audio presence, true peak < 0 dBTP, and every
pending id resolved by `--inputs`. It records a source tree hash, never
freezes a copy.

**Dependencies.** VideoCreator has no image generation, TTS, music or SFX.
The storyboard's audio plan is the brief Creator gives audio-creator; rasters
go through the fitting image-creator leaf. Each is its own released unit.
Reproducing a third-party brand needs the client's permitted-use statement
relayed in `note`.

**PV and series.** A PV or showcase reel of a store, site, product or event
is this leaf, not a separate subject: the same storyboard, improve loop and
render, with the supplied photos, page stills and footage as the picture and
every on-screen fact taken from that material. A series episode names the
approved earlier episode in `series_of`; it shares that episode's look and
ending, opens on its own material, starts from a copy of its source and
gets its own storyboard approval. A model-generated PV is not served.

**Knowledge.** It shares the four pinned HyperFrames technical references
and the kernel's motion vocabulary ("Video authoring references");
create-promotion alone may also use cut-the-curve's seam techniques. Tests:
`scripts/tests/test_create_promotion.py` (render smoke opt-in with
`PROMOTION_RENDER_SMOKE=1`).

## Story family

`video-creator-pipeline/create/story/` serves `create-story`: a short
character story, 10..120 s at 30fps (9:16 default, 16:9, 1:1, 4:5), in
which recurring characters from their approved art act out a narrative
across scenes with dialogue from an approved script and a finished
soundtrack, staged by VideoCreator as 2.5D HyperFrames animation. Always
`kind="work"`; free. It is not a learning explainer with a presenter
(create-explainer-video), a piece presenting a subject (create-promotion)
or a generated MV.

**Why authored, not generated.** Generated video redraws a character on
every shot and drifts from its approved design, and a generated clip has
no shared clock with separately synthesised speech, so lip sync cannot be
aligned. The leaf therefore uses the cast's approved art byte for byte
(pose packs from image-creator's mascot family or supplied images) and
stages speech with poses, expressions and timing; it offers no lip sync
and never claims one. Generated shots may appear only as footage inserts
without a cast member.

**Lifecycle.** The same structure-approval and free-look loop as
create-promotion: Round A writes a storyboard with `## Cast` and a beats
table whose dialogue column quotes lines verbatim; `story.py propose`
checks the cast ids against the `--cast id=PATH` art (a mascot pack counts
only its manifest's passed items), each beat's speaker against the cast on
screen and each quoted line against the approved script, then appends every
cast image's and the script's SHA-256 to the stored storyboard, so the one
approval hash binds them. One Creator-relayed approval releases drafts (up to
8, gap-driven) and the final. `story.py render` runs create-promotion's
render checks through a private instance of its helper (limits 10..120 s,
`story.mp4`), requires every cast member's bound bytes referenced by the
source, checks a script that arrived after approval against the quoted
lines, and checks `mix-caption-N` markup against the Mix sidecar (none may
exist without one). Script, missing poses (a missing-only mascot revise) and voices,
music and SFX (speech per line, then one Mix) are separate units Creator
releases. Tests: `scripts/tests/test_create_story.py`.

## Master family

`video-creator-pipeline/create/master/` serves `create-master`: one finished
delivery master from already-approved parts — up to 24 silent segments
joined in order by cut or dissolve, a finished WAV or audio-creator Mix
bundle laid under them, and optional captions burned in plus an SRT
sidecar, at most 180 s. Always `kind="work"`; free. It covers the finishing
that generate-music-video's supplied mode, several generated clips or cut
promotion pieces need, before legacy `creator-media-assembly`, which keeps
overlays on footage, segments' own sound, ducking and edit-spec trims.

It decides nothing creative and has no proposal round: every part is
already approved and the form is the spec; a missing decision is `Q<n>:`.
Segments must be 8-bit SDR (converting HDR would grade it) and share size
and frame rate with square pixels and no rotation, and the soundtrack must
last the joined picture within one frame (a dissolve shortens it at every
join). A mismatch is a dependency request for
`edit-clip` or audio-creator; this leaf never trims, pads, stretches,
reframes or retimes a part. Segment sound is dropped.

`scripts/master.py build` joins the picture with ffmpeg in one H.264 encode
(CRF 18). The installed ffmpeg has no subtitle or text filter, so burned-in
captions are drawn first by the installed `hyperframes` CLI as a transparent
ProRes 4444 layer in one fixed style (Noto Sans JP, auto-resolved by the
renderer) and composited inside that same encode; the picture never passes
through the browser. A Mix bundle is verified by AudioCreator's own
`verify_bundle` through `mix_audio.py`, then used from re-validated byte
copies, never its mutable paths; its captions are the default caption source, and the final
true peak is checked against its approved ceiling; a plain WAV must stay
below 0 dBTP. Full decode, canvas, fps, duration and audio presence are
checked before the directory is published; a FAIL publishes nothing. Review
is `sheet.png` plus one before/at/after sheet per join; sync, listening and
caption reading speed stay unverified. Tests:
`scripts/tests/test_create_master.py` (the caption render is opt-in with
`MASTER_RENDER_SMOKE=1`).

## Clip family

`video-creator-pipeline/<verb>/clip/` is one short shot, not a generic
film-production workflow. The profile uses the same main/auxiliary model
settings as image-creator and keeps native image vision. Clip does not consult
the HyperFrames references; deterministic families may call HyperFrames through
their own scripts, and no external menu/router is pulled in.

- `generate-clip`: 1-15 seconds, silent single-shot MP4, requested 720p, text
  or one starting image and one appearance reference. Styles are cinematic,
  flat-animation, painted-anime, picture-book, clay, pixel or described.
  Default: 2 variant attempts + 1 corrective total; failures count. Pixel is
  an aesthetic, not a proven sprite grid. Exact model capabilities are checked
  before spending.
- `edit-clip`: trim/contain-or-cover/mute/encode one <=60-second segment.
  MP4/WebM use optional two-pass byte targeting and an actual cap check;
  GIF checks its cap without silently changing size/fps. Never treat GIF repeat
  metadata as a seamless-motion guarantee. Outputs are exclusive and fully
  decoded before publication. Odd exact dimensions are refused; an original
  odd-sized clip is padded up, not cropped down.
- `analyze-clip`: findings on one <=60-second clip, no new video; `deliver`
  may be omitted. Original-file metrics, bounded sample frames and optional
  one-call whole-clip analysis are separate evidence sources. Frame times
  in `frames.json` are seek positions, not exact decoded PTS.

`clip-media.py` is the shared stdlib/ffmpeg helper (`probe`, `frames`, `edit`)
with exclusive output publication, measured byte caps and full decode. GIF
trimming happens before palette generation and palette buffering is bounded.
`free` means zero media-generation calls, not zero reasoning/analysis cost.
Uploading an input image (`upload_inputs`) and remote video analysis
(`remote_analysis`) need separate consent; without it, review is local and
sampled, with temporal/audio quality unverified. Large authorized movies get a
proxy BEFORE the single analysis call; the ~50 MB limit is on base64. xAI
persistent public storage is disabled in this profile; localize temporary URLs
immediately. Edit QA uses the existing helper plus bounded vision checks, not
supplemental inline pixel scripts. No create-clip/source-clip leaf is invented:
authored motion and licensed stock sourcing are separate future families.
Native Telegram interaction and a prolonged soak remain unverified.

Video analysis runs through the `video-analyze-mimo` tool override, which calls
upstream `_download_media` with explicit video options; its tests invoke the
handler with real imports so a registration-only test cannot hide a deferred
ImportError. The old learned `video-render-environment` skill stays on disk but
disabled — it names retired menu leaves.

A failed served clip is a finding, never a silent fallback to the legacy
technic. To withdraw the route, remove the video-creator peer, external skill
root, served-clip routing and multiplex allowlist entry together, then restart
the single gateway; leave artifacts and session state intact and never reset a
working tree over other changes. Bundled hermes-agent residue is retained as
`SKILL.upstream.md`, not an active leaf.
