# Video hands (video-creator)

Ad, music-video, authoring references, tour, explainer-video, promotion, story, master, clip and pixel-animation families of the video hands. Read it when changing or commissioning a video leaf. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`video-creator` receives filled forms on loopback A2A `:9908` (receive-only).
It has video generation/analysis but no TTS, no image generation and no
outbound A2A; it cannot call other hands or peers and returns dependency
requests to the Assistant instead. Shared contract: [`overview.md`](./overview.md).
Every approval below follows the one rule in [`broker.md`](../broker.md)
"Approvals, budget and consent": relayed by the Assistant in the same
conversation, binding bytes, not approver identity.

## Ad family

`ad` belongs to video-creator: `analyze-ad` and `create-ad`.
A generated ad is not a leaf: its picture is text-free generate-clip shots, composed by
create-ad as supplied muted footage with the exact copy, claims, product/logo
rasters and CTA; generated footage never stands in for the product. A PV
authored from supplied material is create-promotion ("Promotion family").
Both leaves use specialist `kind="work"` even though media-generation cost is
free.

An Ad is an audience/promise/action deliverable, not a product-category skill
tree: it addresses a specific audience with a promise and intended action. A
PV primarily introduces a subject's qualities, experience or world. Both
may contain a CTA, so neither CTA presence nor duration alone routes them.
Product categories stay form values, not separate ad skill families.

- `analyze-ad` reads one local <=60-second video for reference or review and
  returns a timeline, construction, persuasion, issues and a production
  handoff. Source claims are quoted as claims, not inherited client facts;
  observations, interpretations and unknowns stay separate. Technical-only
  questions stay `analyze-clip`, even with `what_for: ad`. It never produces
  a new ad; remote video analysis needs separate explicit consent.
- `create-ad` authors a 6..30-second HTML/CSS/GSAP ad (frame rate per
  "Frame rate" below) from approved copy and supplied local assets. Aspect
  (9:16 default, 16:9, 1:1, 4:5; sizes in `ad-render.py`) must match across
  source, preview and output. Changing ratio means re-layout and a separately
  approved plan/source/preview, never a scaled or cropped old composition;
  existing plans keep their bytes and hashes. Theme defaults never authorize
  generating missing assets. It does not generate media, synthesize speech,
  capture, invent metrics or make client-live claims. Client-finished PCM WAV
  and muted supplied MP4 are inputs; raster product/logo files are validated.
- Two approval rounds: the content plan (`plan.json`: exact copy/holds,
  claims, asset hashes, proof samples), then the frozen preview
  (source/checks/frames), before final render. Runtime identity is bound to
  the preview approval; a changed CLI needs a new preview. Static copy checks
  are neither visual readability nor claim verification; final decode and
  visual evidence keep their temporal/listening gaps.
- Audio: distinct finished WAV cues (SFX, music or speech), unity gain,
  framework-owned timing; the decoded true peak is measured and
  silent/undecodable/clipping output is rejected, never normalized. A mixed
  soundtrack uses `audio_workflow: mix` ([`audio.md`](./audio.md) "Mix family").

**Study purpose.** `create-ad` also owns a narrow diagnostic purpose, explicit
`purpose: study` (1..10 s, a concrete question, real copy, no CTA, no Mix),
with its own `freeze-study`/`render-study` commands. A study is never an ad
delivery: output is `study.mp4` with `final_eligible=false`, and the frozen
purpose is bound into plan and preview hashes so it cannot reach final render.
Both purposes have a read-only `preflight --plan --assets` that proves
neither source compatibility nor a visual result; a synthetic smoke fixture
proves plumbing only. Reference video, output frames and jobs stay local and
untracked. Never delete or ignore a stray file (e.g. a Finder `.DS_Store`)
under a frozen root to make a rescan pass.

## Music-video family

`video-creator-pipeline/generate/music-video/` serves `generate-music-video`.
MV is a deliverable, not a collection of character/format skill products.
Subject is a form input; the deliverable is a short MV-style progression
with performance, coherent world and highlights rather than clip's silent
single shot. `video_generate` and `clip-media.py` remain the
generation/finish path, with local style/theme/direction references; no new
provider, wrapper, endpoint, TTS or external skill, and never a menu
generator or cross-media presets.

User shorthand "MV" routes to `generate-music-video`. There is no old-name
alias: `mv_<slug>` output filenames and frozen jobs stay unchanged; active
older jobs are reissued under a new proposal and approval, never edited. The
form's front matter prefix rule lives in [`overview.md`](./overview.md)
"The form (front matter is the only representation)".

- Style, theme and direction options (all accept free text) live in
  `generate/music-video/SKILL.md`; they are authored recipes, not
  live-render-certified presets. Looks are described by traits, never by a
  studio, director or artist name. A theme is a starting point, not an
  immutable look; `theme_detail`/`must_keep` override it.
- Pace and transition are reference-backed and carried by prompt and QA, not
  just the form. A tempo change requires renewed approval and never resets the
  spent allowance; approved plans keep their frozen timing. Exact cut
  timing/BPM is not guaranteed and a global post-render speedup is no
  substitute for the requested direction. Source-specific START/CROSS/AFTER
  spatial relations are explicit in the proposal
  (`references/spatial-direction.md`); failed critical motion stays a quality
  gap even when objects and styles match.
- Round A writes a new `proposal-v<N>.md` (world, identity lock, beats, input
  hashes, actual prompt/backend limits, sound/finishing choices, consents, call
  allowance) with zero media-generation or remote-analysis calls. A budget
  alone never authorizes generation. The exact prompt is a separate file
  (1..1800 UTF-8 bytes — a conservative limit for the current chain, not a
  provider guarantee), hashed before approval and rechecked before submission;
  changed prompt text is reapproved, failed attempts are never silently
  refunded or retried.
- Supplied music need not exist for Round A: a textual `music_plan` makes the
  proposal `pending-inputs` with `can_generate: false`; pending
  character-image upload consent likewise permits only local planning. The
  Assistant obtains the separate music release (music is never produced in
  this leaf), then supplies the real `music_file` and consents for a NEW
  numbered proposal and approval. Never mutate or execute the preliminary
  proposal, invent a WAV/hash, reset attempts or re-ask the accepted direction.
- Round B continues the same work conversation with the exact `approved_plan`
  path and `approval_sha256`; only that match releases generation, and a
  changed input or creative choice needs a new proposal. Default 2 variants +
  1 corrective counts every tool invocation including failures; unknown
  results are reconciled, never blindly retried; the allowance never resets on
  resume.
- Audio modes: generated (only when the actual backend advertises native audio
  — the xAI-first chain does not, so it stays blocked, never guessed),
  supplied (silent visual master for separately approved assembly) or silent.
  Reference videos and supplied music are never uploaded; character-image
  upload consent and remote-analysis consent stay separate.
- xAI's reference-image path silently clamps to 10 s even though its general
  capabilities say 15 s. Default 10 s with `character_reference`, otherwise
  15 s; block an explicitly longer reference-mode request before spend. Never
  change the input's role to starting frame or drop it merely to bypass this.
- Exact text needs a text-free base and separately agreed finishing; exact
  lyric/beat/lip sync is not promised. No required finish with an unknown route
  may be hidden until after spend. A silent visual master is not a completed
  musical MV. A MiniMax mention does not reconfigure the xAI-first chain or
  justify pretending an output used that model.
- QA covers identity, world, performance/progression, text/audio policy,
  technical decode and budget evidence; temporal/audio QA stays explicitly
  unverified (sampled frames and decode do not establish motion, continuity or
  sound quality). Declined/failed remote analysis stays UNVERIFIED; model audio
  findings are not human listening. Shot isolation or multi-shot production
  needs its own release/allowance, never a hidden expansion of one MV call.

## Video authoring references

`video-creator`'s `skills.external_dirs` pins four individual technical
directories — `hyperframes-core`, `hyperframes-animation`, `cut-the-curve`,
`oversized-cursor` — from `~/.agents/skills`, never the whole store (the rule
and its why: [`AGENTS.md`](../../AGENTS.md) "Skills"). They are separate from
the knowledge-only craft pins ([`overview.md`](./overview.md) "Media craft
knowledge"). Only `create-tour`, `create-ad`, `create-promotion`,
`create-story` and the HyperFrames path of `create-explainer-video` may
consult them, per `video-creator-pipeline/references/hyperframes.md`; clip, MV
and analyze-ad do not, and Motion Canvas uses only its own local reference.

They are optional, read-only background — never a new approval gate, workflow
or leaf, and never a substitute for a leaf's form fields, helpers or approvals.
The restriction to those leaves is enforced by each leaf's Procedure, not a
tool-permission sandbox. A missing, unreadable or ambiguous reference is
reported (one lookup per resource) and the leaf authors locally for that
topic; a real CLI/dependency failure or failed approval/validation check still
blocks. A config change needs a fresh session.

**Frame rate.** create-promotion, create-story, create-ad, create-tour and
the HyperFrames path of create-explainer-video render at an allowed rate from
one list in `video-creator-pipeline/scripts/frame_rate.py`. Omitted means 30
and is never written into a plan, so frozen plans, proposals and forms keep
their bytes and hashes. The rate is part of the approved plan: a changed rate
needs a new approval, like a changed aspect. Promotion and story drafts render
capped at 30 to keep the improve loop fast; GSAP motion is time-based, so
draft and final differ only in sampling. Motion Canvas stays 30-only (its
frame-count, timeout and preview-equality checks assume it). create-master
needs every segment at one shared rate; mixed rates go through edit-clip first.

**Motion vocabulary.** The kernel's `references/motion-vocabulary.md` is read
by all five authored leaves (Motion Canvas uses names and looks only) before
the plan that fixes their beats; they name its entries instead of generic
"fade", "slide" or "card". It adds no plan field, schema or rule; a leaf's
`style` option stays its own reference, and a drawn look never re-renders
supplied art, a cast or a logo. Why it stays rule-free: "Storyboard
vocabulary" under the Promotion family.

**Three graphics** is an opt-in (`graphics: three-webgl2`) on create-tour,
create-ad and the HyperFrames path of create-explainer-video — not a third
explainer renderer or a new video subject. It selects one synchronous WebGL2
canvas with procedural Three.js and custom GLSL under the same paused GSAP
clock (`video-creator-pipeline/references/three-graphics.md`). The engine pins
its own HyperFrames, Three, esbuild, puppeteer-core and Node plus a dedicated
cloned browser with a fixed software backend (`engines/three-webgl/`); never
use or downgrade the mutable global CLI for these jobs. `setup.mjs` is
maintainer-only; jobs only stage verified assets through `three_graphics.py`
and never install, upgrade or change the GPU mode. Opted-in tours require an
explicit `screen_mode`/v3 and an approved preview; preview binds
runtime/layer evidence and render-log errors fail the job even when the CLI
exits zero. Pixel equality is not artistic acceptance: inspect encoded motion
and native UI crops. Not authorized: async loaders, addons, WebGPU,
history-dependent simulation, hardware fallback, global install, or any change
to prior frozen jobs. Fixtures are engineering tests, not user approvals.

## Tour family

`video-creator-pipeline/create/tour/` serves `create-tour`: bounded (<=60 s)
task-local authored UI walkthroughs — recreate from reference/design/text, edit
supplied local footage, or capture an explicitly approved sanitized Web demo —
with frozen source projects, exclusive preview/final directories and a safe
approval resume.
The Assistant owns what_for/audience, semantic flow, fidelity and choice approvals;
VideoCreator authors task-local HTML/CSS/GSAP, state changes and camera/pointer
from approved reference images, design and text. No per-step screenshots or
client-written steps JSON are required. Frame and decorative background are
separate from faithful product internals; simplified UI is explicitly
approved/labeled, never invented real-product functionality.

Intro/outro default ON (title-reveal/result-hold); the references are examples
with `other: true`, not presets. Free-text directions stay verbatim; only an
explicit "none" omits them, and ambiguity goes back as one clarification, never
a nearest-preset fallback.

Reference is inspiration/context, source is actual local footage, target is an
operation destination; they are distinct and none of them is consent.
`screen_mode` is recreate (omitted preserves v2 behavior), supplied or capture;
explicit modes use v3 proposal/hash approval without migrating frozen v1/v2
artifacts. Narration consumes finished audio-creator WAV plus current
`words.json`; Tour makes no edits to frozen source, external runtime
workflows/executables or TTS.

The Assistant always routes this free leaf with `specialist_call(kind="work")`,
never raw A2A or a direct resident script. `authored.py` freezes v2/v3
source/contract/form, checks real renders and publishes fresh preview/final
evidence with full decode; it never generates layout/UI or enumerates UI
actions. `tour.py` remains for persisted v1 screenshot projects only. Authoring
happens in task-local source, never managed scripts or frozen projects. Helpers
are not a sandbox for untrusted downloaded HTML; source must be reviewed before
execution. The skill-authoring validator's directory-name warning is
intentional: Hermes names nested leaves `<verb>-<subject>`.

Projects freeze source copies and hashes. Preview=yes authors/freezes/checks/
snapshots only; client approval resumes that unchanged project into a fresh
final directory, and changed fields need a new project/preview. Existing
runtime data, inputs, deliveries and failed evidence are never deleted or
overwritten. Render/decode and sampled contrast/layout evidence are distinct
from human task correctness, temporal quality and listening.

Tests: `test_tour.py` (v1), `test_authored_tour.py` (v2), `test_tour_footage.py`
(v3), fixtures under `scripts/tests/fixtures/{authored-tour,captured-tour}/`
(variants are test cases, not production presets). Synthetic render tests are
not product-live evidence; fixture renders are opt-in: a fresh scratch
directory and already-installed tools, no installs.

Rollout: profile skill roots are already linked, so new children are visible;
do not run the project-wide installer just to refresh this leaf, and use a fresh
work session. Roll back without rewriting data: route new work to recreate,
stop only owned capture sessions, preserve private evidence, and never delete or
downgrade existing v3 projects — render them with the version that created them.

### Footage And Capture v3

The same leaf preserves frame/style/background/backdrop/free-text intro/outro.
The Assistant proposes semantic steps from goal/audience/start_state and optional flow;
clients need not write action scripts. An explicit mode first returns only
`proposal-vN.md` and SHA-256. The proposal's `tour` block binds the normalized
form and capture scope. Approved reconnaissance
precedes approved stateful recording. Changed scope needs a new proposal, not
per-click approval inside the existing scope. Exact preview approval remains a
separate final gate.

`footage.py` fully decodes and trims local raw video at 1x, validates bounded
source ranges, and records explicit keep/mute audio and source-to-timeline
mapping. `<video>` remains moving footage, with unique id, muted/playsinline
and framework-owned timing; keep uses a separate timed audio element. No
screenshot replacement, fabricated event timings or double cursor. Raw/source
hashes, proposal and logs stay private, outside final.

`capture.py` owns isolated, sanitized Web recording through installed
agent-browser via the existing terminal surface. It binds a private
namespace/session to the job/proposal lease under an exclusive flock, caps
reconnaissance and recording takes per job (failures counted across proposal
versions), checks origin/tab state before/after actions, rejects arbitrary
eval/navigation/login/upload and unapproved selectors/data, and fsyncs pending
action evidence before dispatch. Interruptions retain raw/unknown actions;
recovery closes only the owned session and cannot replay an interrupted
approval. SIGKILL cleanup relies on a private idle timeout and explicit lease
recovery, not a finally-block promise. Recon under the exact current proposal
is mandatory; no consent or evidence is relabeled/reused, and new proposals
cannot reset either budget or permit an extra take.

Launch capture/recon/recovery with terminal `background: true` and
`notify: true`; wait only on that process. A long scope exceeds the 180 s
foreground timeout, so never retry a killed foreground recording as a
workaround. Background timeout is not a lifetime cap: supervise with bounded
waits, then terminate only the owned process and reconcile its lease; never
replay interrupted approvals or launch a duplicate after a wait timeout.

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
its own reference `create/explainer-video/references/motion-canvas.md`, with
no dependency on the external HyperFrames skills. Prefer Motion Canvas for
reactive diagrams, algorithms and Canvas-based explanation; prefer HyperFrames
for HTML/UI or media-oriented compositions. Both render 16:9 or 9:16;
HyperFrames at the plan's frame rate ("Frame rate" above), Motion Canvas only
at 30 fps. A `version: 1` plan naming `motion-canvas` stays non-executable: it
needs a fresh `version: 2` proposal and approval, never a resume of the old
hash. An unsupported requested renderer is a capability finding, not an
automatic switch between engines or to legacy `creator-manim-explainer`, which
a request for explicit Manim or its mathematical/3D scope still retains.

**Performance fields.** `framing` (none / bust / full) is independent of
`performance` (still / puppet / animated) and `lip_sync` (off / cues / baked).
Bust only _proposes_ lip-sync cues by default, never a silent substitute for an
explicit `off`; full supports only the performance the client approved. Neither
renderer provides phoneme/viseme inference, rig authoring or native
talking-model playback. Two supported routes: authored cue JSON plus mouth
PNGs drive a deterministic mouth track, or a supplied finished muted MP4
carrying its own sync evidence. A missing required performance asset is
`pending-inputs`, never a silent downgrade.

**Characters and dependencies.** The Assistant, never VideoCreator, resolves
characters: a library character through the `characters` tool (only its
approved package content is canon, never a draft or archive); otherwise a
direct path or identity the Assistant already holds, else a bounded name-only
lookup in the caller's own workspace, with an ambiguous match going back as a
question. Never do a broad home-directory scan or invent a character because a
file is missing. Explicit assets are kept as unchanged originals; resolved
roots and private asset names never enter a public proposal, form or report.
An unspecified character is not "no character": the Assistant clarifies. A
missing pose becomes a missing-only request through image-creator's mascot
leaf, preserving the approved identity. Script text goes through Writer's
`write-script` family, never the Assistant or Creator composing it; grounding
through researcher; narration/audio through audio-creator. VideoCreator
returns a dependency request, released as its own separately approved unit.

**Lifecycle.** `propose` writes `plan.json` + `proposal.md` + an assets
snapshot and returns `pending-inputs` or `awaiting-approval` with the proposal
SHA-256; missing inputs are described in `spec.pending`, never invented files
or hashes. The approved script and exact on-screen copy are settled inputs. A
proposal is ready only once the selected modes' required inputs and a supported
renderer are in hand. After approval, `freeze` and `snapshot` run, and only a
matching `render` against the approved preview hash releases the final video
(flags: the leaf's Procedure). Nothing self-approves; frozen projects and
delivered outputs are never rewritten.

**References.** A HyperFrames plan uses the curated external references under
their read-only policy ("Video authoring references" above); a Motion Canvas
plan uses only its own local reference and the pinned local runtime. A missing
reference is reported with a local-authoring fallback, never a blocker, while
real runtime or approval errors still block.

**Motion Canvas runtime.** The maintainer provisions it explicitly with
`engines/motion-canvas/setup.mjs`; jobs never install or upgrade it. Setup
clones a supplied browser into ignored `runtime/browser/` (avoiding a Dock
clash with the everyday browser) and never copies cookies or a profile, so
every render gets a fresh isolated one. Rerunning setup never overwrites a
different clone or changed lock — that drift needs explicit maintainer
replacement. Every preview records the actual runtime/Node/browser identity;
any identity change needs a fresh preview and approval. Scenes are trusted
authored code, not a hostile-JavaScript sandbox. Reactive visual bindings use
the view's `globalTime` signal, not generator-thread-only `useTime()`. On
HyperFrames, the generated mouth track declares a function the scene calls
(HyperFrames coalesces inline scripts after external files), and each cue
boundary writes each mouth once to avoid reverse-seek ordering conflicts.

Final QA always carries the engine's contrast-audit status; Motion Canvas has no
automated contrast check and reports "requires manual visual review". Synthetic
fixtures are technical evidence only, not real speech/character quality or
live Assistant-to-hands handoff proof.

## Promotion family

`video-creator-pipeline/create/promotion/` serves `create-promotion`:
authored promotion video — launch/promo, brand or sizzle pieces, feature
reveals, kinetic typography, logo stings — 3..60 s (frame rate per "Frame
rate"), 16:9 (default), 9:16, 1:1 or 4:5, that VideoCreator designs and draws
itself in HTML/CSS/SVG/GSAP, optionally matching a local reference video
(`reference_use: inspiration | reproduce`). Always `kind="work"`; free. It
exists because no other served leaf fits a launch/promo piece (ad needs
approved assets and a CTA, tour is a UI walkthrough, explainer a learning
goal).

**Structure approval, free look.** The approval covers structure only — beats,
timing, verbatim copy, seams, audio plan and the look in words — never pixel
sizes. The look is an explicit improve loop of up to 8 gap-driven drafts: each
renders a `compare.png` (reference above, draft below, same relative
positions), and VideoCreator writes the biggest gaps against the reference and
the leaf's `<Standard>` and fixes them by redesign. The `vision-window` plugin
limits a step to three images. Why:
[decisions/explainer-structure-approval.md](../decisions/explainer-structure-approval.md).

**Storyboard vocabulary.** The storyboard decides the film's taste, not the
implementer. Round A therefore reads the kernel's `references/motion-vocabulary.md`
(names, looks and usual builds, no rules) and names its entries in the
storyboard instead of generic "fade" or "card". Keep the vocabulary rule-free:
[decisions/storyboard-vocabulary-rule-free.md](../decisions/storyboard-vocabulary-rule-free.md).

**Lifecycle.** Round A writes `storyboard.md`; `promotion.py propose` stores it
as `proposal-vN/storyboard.md` with its SHA-256 and `awaiting-approval` /
`pending-inputs`. One Assistant-relayed approval releases authoring, drafts and
the final. `render --quality final` verifies the hash, canvas/duration, no
remote references and strict lint, renders with the installed `hyperframes`
CLI, then checks canvas, fps, duration, audio presence, true peak < 0 dBTP and
that every pending id was resolved. It records a source tree hash, never
freezes a copy.

**Dependencies.** VideoCreator has no image generation, TTS, music or SFX.
The storyboard's audio plan is the brief the Assistant gives audio-creator;
rasters go through the fitting image-creator leaf. Each is its own released
unit. Reproducing a third-party brand needs the client's permitted-use
statement relayed in `note`.

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
character story, 10..120 s (frame rate per "Frame rate"; 9:16 default, 16:9,
1:1, 4:5), in which recurring characters from their approved art act out a
narrative across scenes with dialogue from an approved script and a finished
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
table whose dialogue column quotes lines verbatim; `story.py propose` checks
cast ids against the `--cast id=PATH` art (a mascot pack counts only its
manifest's passed items), each beat's speaker against the cast on screen and
each quoted line against the approved script, then appends the cast images'
and script's SHA-256 so the one approval hash binds them. `story.py render`
reuses create-promotion's render checks, requires every cast member's bound
bytes referenced by the source, re-checks a script that arrived after
approval, and checks `mix-caption-N` markup against the Mix sidecar. Script,
missing poses and voices/music/SFX (speech per line, then one Mix) are
separate units the Assistant releases. Tests: `test_create_story.py`.

## Master family

`video-creator-pipeline/create/master/` serves `create-master`: one finished
delivery master from already-approved parts — silent segments joined in order
by cut or dissolve, a finished WAV or audio-creator Mix bundle laid under
them, and optional captions burned in plus an SRT sidecar. Always
`kind="work"`; free. It covers the finishing that generate-music-video's
supplied mode, several generated clips or cut promotion pieces need, before
legacy `creator-media-assembly`, which keeps overlays on footage, segments' own
sound, ducking and edit-spec trims.

It decides nothing creative and has no proposal round: every part is already
approved and the form is the spec; a missing decision is `Q<n>:`. Segments
must be 8-bit SDR only (converting HDR would grade it) and share size and
frame rate with square pixels and no rotation, and the soundtrack must last
the joined picture within one frame (a dissolve shortens it at every join). A
mismatch is a dependency request for `edit-clip` or audio-creator; this leaf
never trims, pads, stretches, reframes or retimes a part. Segment sound is
dropped.

`scripts/master.py build` joins the picture with ffmpeg in one H.264 encode.
The installed ffmpeg has no subtitle or text filter, so burned-in captions are
drawn first by the installed `hyperframes` CLI as a transparent layer and
composited inside that same encode; the picture never passes through the
browser. A Mix bundle is verified by AudioCreator's own `verify_bundle` through
`mix_audio.py`, then used from re-validated byte copies, never its mutable
paths; its captions are the default caption source, and the final true peak is
checked against its approved ceiling (a plain WAV must stay below 0 dBTP). Full
decode, canvas, fps, duration and audio presence are checked before the
directory is published; a FAIL publishes nothing. Sync, listening and caption
reading speed stay unverified. Tests: `test_create_master.py`.

## Clip family

`video-creator-pipeline/<verb>/clip/` is one short shot, not a generic
film-production workflow. The profile uses the same main/auxiliary model
settings as image-creator and keeps native image vision. Clip does not consult
the HyperFrames references; deterministic families may call HyperFrames through
their own scripts, and no external menu/router is pulled in.

- `generate-clip`: silent single-shot MP4, text or one starting image and one
  appearance reference. Default: 2 variant attempts + 1 corrective total;
  failures count. Pixel is an aesthetic, not a proven sprite grid. Exact model
  capabilities are checked before spending.
- `edit-clip`: trim/contain-or-cover/mute/encode one <=60-second segment.
  MP4/WebM use optional two-pass byte targeting and an actual cap check;
  GIF checks its cap without silently changing size/fps and never promises
  seamless-loop motion. Outputs are exclusive and fully decoded before
  publication. Odd exact dimensions are refused; an original odd-sized clip is
  padded up, not cropped down.
- `analyze-clip`: findings on one <=60-second clip, no new video; `deliver`
  may be omitted. Original-file metrics, bounded sample frames and optional
  one-call whole-clip analysis are separate evidence sources. Frame times
  in `frames.json` are seek positions, not exact decoded PTS.

`clip-media.py` is the shared stdlib/ffmpeg helper (`probe`, `frames`, `edit`)
with exclusive output publication, measured byte caps and full decode.
`free` means zero media-generation calls, not zero reasoning/analysis cost.
Uploading an input image (`upload_inputs`) and remote video analysis
(`remote_analysis`) need separate consent; without it, review is local and
sampled, with temporal/audio quality unverified. Large authorized movies get a
proxy BEFORE the single analysis call; the ~50 MB limit is on base64. xAI
persistent public storage is disabled in this profile; localize temporary URLs
immediately. Edit QA uses the existing helper plus bounded vision checks, not
supplemental inline pixel scripts. No create-clip/source-clip leaf is invented:
authored motion and licensed stock sourcing are separate families.

Video analysis runs through the `video-analyze-mimo` tool override, which calls
upstream `_download_media` with explicit video options; its tests invoke the
handler with real imports so a registration-only test cannot hide a deferred
ImportError.

A failed served clip is a finding, never a silent fallback to the legacy
technic. To withdraw the route, remove the video-creator peer, external skill
root and served-clip routing together and restart the single gateway; leave
artifacts and session state intact.

## Pixel-animation family

`video-creator-pipeline/create/pixel-animation/` carries one verb.
`create-pixel-animation` delivers a grid-exact pixel animation (sprite or cel
cycle, character loop, logo or scene loop, environmental effect, integer-step
parallax) as an RGB-lossless master MP4, a yuv420p compatibility MP4 and an
optional GIF, with palette, cadence and loop seam verified numerically on the
encoded files; nothing is generated by a model and it is free. A model-made
clip with a pixel look is `generate-clip`, which guarantees no grid. It does
not draw a still from scratch when the still is the deliverable (that is
image-creator's `create-pixel-art`, whose native PNG and `palette.json` may be
this leaf's `source`). Always `kind="work"`; no proposal round.

- **`cels.py`:** `draw` renders `frame_*.json` cell maps (the shape of
  `create-pixel-art`'s `pixel.py draw`) into numbered native PNG frames in a
  new directory, refusing mixed palettes or sizes and an existing `--out`;
  `sheet` builds a contact sheet with ImageMagick `+append`, never `montage`.
- **`encode-pixel-video.sh`:** nearest-neighbour integer scaling only. The
  container fps is an integer multiple of the effective fps, so every native
  frame is held equally.
- **`verify-pixel-video.py`:** decodes the encoded file and checks scale, grid,
  palette, block uniformity, fps with equal holds, the loop seam and, for the
  master, identity with the native source frames; exits non-zero on failure.

Tests: `scripts/tests/test_create_pixel_animation.py` (the end-to-end encode
and verify skip without `ffmpeg` or `uv`).
