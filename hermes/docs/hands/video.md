# Video hands (video-creator)

Ad, music-video, authoring references, tour, explainer-video, promotion, story, master, clip and pixel-animation families of the video hands. Read it when changing or commissioning a video leaf. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`video-creator` receives filled forms on loopback A2A `:9908` (receive-only).
It has video generation/analysis but no TTS, no image generation and no
outbound A2A; it cannot call other hands or peers and returns dependency
requests to the Assistant instead. Shared contract: [`overview.md`](./overview.md).
Every approval below follows the one rule in [`broker.md`](../broker.md)
"Approvals, budget and consent": relayed by the Assistant in the same
conversation, binding bytes, not approver identity. Forms, options and flags:
each leaf's `SKILL.md` and `references/` under
`profiles/video-creator/skills/video-creator-pipeline/`.

## Ad family

`ad` belongs to video-creator: `analyze-ad` and `create-ad`.
A generated ad is not a leaf: its picture is text-free generate-clip shots,
composed by create-ad as supplied muted footage with the exact copy, claims,
product/logo rasters and CTA; generated footage never stands in for the
product. A PV authored from supplied material is create-promotion ("Promotion
family"). Both leaves use specialist `kind="work"` even though media-generation
cost is free.

An Ad is an audience/promise/action deliverable, not a product-category skill
tree; a PV introduces a subject's qualities, experience or world. Both may
contain a CTA, so neither CTA presence nor duration alone routes them. Product
categories stay form values, never separate ad skill families.

- `analyze-ad` reads one local video for reference or review and returns a
  production handoff. Source claims are quoted as claims, not inherited client
  facts. Technical-only questions stay `analyze-clip`. It never produces a new
  ad; remote video analysis needs separate explicit consent.
- `create-ad` authors an HTML/CSS/GSAP ad from approved copy and supplied
  local assets (frame rate: "Frame rate" below). Changing aspect means
  re-layout and a separately approved plan/source/preview, never a scaled or
  cropped old composition. Theme defaults never authorize generating missing
  assets. It does not generate media, synthesize speech, capture, invent
  metrics or make client-live claims.
- Two approval rounds: the content plan (exact copy, claims, asset hashes),
  then the frozen preview, before final render. Runtime identity is bound to
  the preview approval; a changed CLI needs a new preview.
- Audio: finished WAV cues at unity gain; silent/undecodable/clipping output is
  rejected, never normalized. A mixed soundtrack uses `audio_workflow: mix`
  ([`audio.md`](./audio.md) "Mix family").

**Study purpose.** `create-ad` also owns a narrow diagnostic `purpose: study`
with its own `freeze-study`/`render-study`. A study is never an ad delivery:
output carries `final_eligible=false` and the frozen purpose is bound into the
plan and preview hashes so it cannot reach final render. Never delete or ignore
a stray file (e.g. `.DS_Store`) under a frozen root to make a rescan pass.

## Music-video family

`video-creator-pipeline/generate/music-video/` serves `generate-music-video`.
MV is a deliverable, not a collection of character/format skill products: a
short MV-style progression with performance, a coherent world and highlights,
unlike clip's silent single shot. No new provider, wrapper, endpoint, TTS or
external skill, and never a menu generator or cross-media presets.

User shorthand "MV" routes to `generate-music-video`. There is no old-name
alias: `mv_<slug>` output filenames and frozen jobs stay unchanged; active
older jobs are reissued under a new proposal and approval, never edited.
Front-matter prefix rule: [`overview.md`](./overview.md) "The form (front
matter is the only representation)".

- Style, theme and direction options live in the leaf's `SKILL.md`; they are
  authored recipes, not live-render-certified presets. Looks are described by
  traits, never by a studio, director or artist name.
- Pace and transition are carried by prompt and QA, not just the form. A tempo
  change requires renewed approval and never resets the spent allowance. A
  post-render speedup is no substitute for the requested direction, and failed
  critical motion stays a quality gap even when objects and styles match.
- Round A writes a new `proposal-v<N>.md` with zero media-generation or
  remote-analysis calls; a budget alone never authorizes generation. The exact
  prompt is a separate hashed file, rechecked before submission; changed prompt
  text is reapproved, failed attempts are never silently refunded or retried.
- Supplied music need not exist for Round A: a textual `music_plan` (or pending
  character-image upload consent) makes the proposal `pending-inputs`. The
  Assistant obtains the music (never produced in this leaf), then supplies the
  real file and consents for a NEW numbered proposal. Never mutate or execute
  the preliminary proposal, invent a WAV/hash or reset attempts.
- Round B continues the same work conversation with the exact `approved_plan`
  path and `approval_sha256`; only that match releases generation. The
  allowance counts every invocation including failures, unknown results are
  reconciled, never blindly retried, and it never resets on resume.
- Audio is generated only when the actual backend advertises native audio (the
  xAI-first chain does not, so it stays blocked, never guessed). Reference
  videos and supplied music are never uploaded; character-image upload consent
  and remote-analysis consent stay separate.
- xAI's reference-image path silently clamps to 10 s although its capabilities
  say 15 s: block a longer reference-mode request before spend, and never
  change the input's role or drop it merely to bypass this.
- Exact text needs a text-free base and separately agreed finishing; exact
  lyric/beat/lip sync is not promised. No required finish with an unknown route
  may be hidden until after spend. A silent visual master is not a completed
  musical MV. A MiniMax mention does not reconfigure the xAI-first chain.
- Temporal/audio QA stays UNVERIFIED. Multi-shot production needs its own
  release/allowance, never a hidden expansion of one MV call.

## Video authoring references

`video-creator`'s `skills.external_dirs` pins four individual technical
directories — `hyperframes-core`, `hyperframes-animation`, `cut-the-curve`,
`oversized-cursor` — from `~/.agents/skills`, never the whole store (rule and
why: [`AGENTS.md`](../../AGENTS.md) "Skills"). They are separate from the
knowledge-only craft pins ([`overview.md`](./overview.md) "Media craft
knowledge"). Only `create-tour`, `create-ad`, `create-promotion`,
`create-story` and the HyperFrames path of `create-explainer-video` may consult
them, per `video-creator-pipeline/references/hyperframes.md`; clip, MV and
analyze-ad do not, and Motion Canvas uses only its own local reference.

They are optional, read-only background — never a new approval gate, workflow
or leaf, never a substitute for a leaf's form fields, helpers or approvals. The
leaf restriction is enforced by each leaf's Procedure, not a tool-permission
sandbox. A missing or ambiguous reference is reported and the leaf authors
locally; a real CLI/dependency failure or failed approval check still blocks.

**Frame rate.** The authored HyperFrames leaves (promotion, story, ad, tour,
explainer's HyperFrames path) render at a rate from the one list in
`video-creator-pipeline/scripts/frame_rate.py`. Omitted means 30 and is never
written into a plan, so frozen plans, proposals and forms keep their bytes and
hashes. The rate is part of the approved plan: a change needs a new approval,
like a changed aspect. Promotion and story drafts render capped at 30 (GSAP
motion is time-based, so draft and final differ only in sampling). Motion
Canvas stays 30-only; create-master needs every segment at one shared rate, so
mixed rates go through edit-clip first.

**Motion vocabulary.** The kernel's `references/motion-vocabulary.md` is read
by the five authored leaves before the plan that fixes their beats; they name
its entries instead of generic "fade" or "card". It adds no plan field, schema
or rule, and a drawn look never re-renders supplied art, a cast or a logo.
Why: "Storyboard vocabulary" under the Promotion family.

**Three graphics** is an opt-in (`graphics: three-webgl2`) on create-tour,
create-ad and the HyperFrames path of create-explainer-video — not a third
explainer renderer or a new video subject; details in
`video-creator-pipeline/references/three-graphics.md`. Rules to keep:

- The engine pins its own toolchain and a dedicated cloned browser
  (`engines/three-webgl/`); never use or downgrade the mutable global CLI for
  these jobs. `setup.mjs` is maintainer-only; jobs never install, upgrade or
  change the GPU mode.
- Opted-in tours require an explicit `screen_mode`/v3 and an approved preview.
  Render-log errors fail the job even when the CLI exits zero.
- Not authorized: async loaders, addons, WebGPU, history-dependent simulation,
  hardware fallback, or any change to prior frozen jobs.

## Tour family

`video-creator-pipeline/create/tour/` serves `create-tour`: bounded
task-local authored UI walkthroughs — recreate from reference/design/text, edit
supplied local footage, or capture an explicitly approved sanitized Web demo —
with frozen source projects and exclusive preview/final directories. It is not
an explainer (learning goal), ad or promotion.

- The Assistant owns what_for/audience, semantic flow, fidelity and choice
  approvals; VideoCreator authors task-local HTML/CSS/GSAP from them. No
  per-step screenshots or client-written steps JSON.
- Frame and decorative background are separate from faithful product
  internals; simplified UI is approved/labeled, never invented real-product
  functionality.
- Style/intro/outro references are examples, not presets: free-text directions
  stay verbatim and ambiguity goes back as one clarification, never a
  nearest-preset fallback.
- Reference (inspiration), source (actual local footage) and target
  (operation destination) are distinct and none of them is consent.
  Explicit `screen_mode` uses v3 proposal/hash approval without migrating
  frozen v1/v2 artifacts (omitted preserves v2). Narration consumes finished
  audio-creator WAV plus `words.json`; Tour makes no TTS.
- Always `specialist_call(kind="work")`, never raw A2A or a direct resident
  script. `authored.py` freezes and checks; it never generates layout/UI.
  `tour.py` remains for persisted v1 screenshot projects only. Authoring
  happens in task-local source, never managed scripts or frozen projects.
  Helpers are not a sandbox for untrusted downloaded HTML: review source
  before execution.
- Preview=yes authors/freezes/checks only; approval resumes that unchanged
  project into a fresh final directory, and changed fields need a new
  project/preview. Existing data, deliveries and failed evidence are never
  deleted or overwritten; v3 projects are never downgraded (render them with
  the version that created them). Render/decode and sampled contrast evidence
  are distinct from human task correctness, temporal quality and listening.

### Footage And Capture v3

The Assistant proposes semantic steps from goal/audience/start_state; an
explicit mode first returns only `proposal-vN.md` and its SHA-256, whose `tour`
block binds the normalized form and capture scope. Approved reconnaissance
precedes approved stateful recording. A changed scope needs a new proposal, not
per-click approval inside the existing one; exact preview approval stays a
separate final gate.

- `footage.py` trims local raw video at 1x. `<video>` stays moving footage; no
  screenshot replacement, fabricated event timings or double cursor. Raw/source
  hashes, proposal and logs stay private, outside final.
- `capture.py` owns isolated, sanitized Web recording through the installed
  agent-browser, under a lease bound to the job/proposal. Recon and recording
  takes are capped per job and failures count across proposal versions: no
  consent or evidence is relabeled or reused and a new proposal cannot reset a
  budget or permit an extra take. Recon under the exact current proposal is
  mandatory. Recovery closes only the owned session and never replays an
  interrupted approval; SIGKILL cleanup relies on an idle timeout plus lease
  recovery, not a finally-block promise.
- Launch capture/recon/recovery with terminal `background: true` and
  `notify: true`: a long scope exceeds the foreground timeout, so never retry a
  killed foreground recording or launch a duplicate.
- This is a wrapper boundary, NOT a terminal/website sandbox: existing terminal
  access can bypass it and operating contracts forbid bypass. Origin/tab checks
  do not make arbitrary sites safe (page scripts can mutate state; redirects can
  load before detection). Only approved controlled sanitized demos qualify; no
  authenticated/private-region capture and no privacy redaction is claimed —
  source crops are decorative. No new plugin/toolset or broad
  browser/computer_use grant exists.
- Native capture is UNAVAILABLE: cua-driver's `start_recording` captures the
  main display, not a scoped window, and no cross-profile desktop-action guard
  covers Assistant's `computer_use`. It stays blocked until window-scoped
  capture AND a shared guard are proven. Never grant `computer_use` to
  VideoCreator or route around this through Assistant or full-desktop capture.

## Explainer-video family

`video-creator-pipeline/create/explainer-video/` serves `create-explainer-video`:
a bounded local-authored explanation of a topic, for an audience, toward a
`learning_goal` — never a UI walkthrough (`create-tour`), an ad (`create-ad`), a
model-generated MV (`generate-music-video`) or a talking-model product. Always
`specialist_call(kind="work")`, even though the leaf is `cost: free`.

**Renderer.** The engine is an explicit choice made in the proposal and
preserved — never silently switched, including on failure. `renderer:
hyperframes` (plan `version: 1`) authors HTML/CSS/GSAP; `renderer:
motion-canvas` (plan `version: 2`) authors a Motion Canvas scene through the
pinned runtime in `engines/motion-canvas/`, with its own reference
`create/explainer-video/references/motion-canvas.md` and no dependency on the
external HyperFrames skills. A `version: 1` plan
naming `motion-canvas` stays non-executable: it needs a fresh `version: 2`
proposal and approval, never a resume of the old hash. An unsupported renderer
is a capability finding, not an automatic switch between engines or to legacy
`creator-manim-explainer`, which explicit Manim or mathematical/3D scope still
retains.

**Performance fields.** `framing` (none / bust / full) is independent of
`performance` (still / puppet / animated) and `lip_sync` (off / cues / baked).
Bust only _proposes_ lip-sync cues by default, never a silent substitute for an
explicit `off`. Neither renderer provides phoneme/viseme inference or rig
authoring; sync comes from authored cue JSON plus mouth PNGs or a supplied
muted MP4 carrying its own sync evidence. A missing required performance asset
is `pending-inputs`, never a silent downgrade.

**Characters and dependencies.** The Assistant, never VideoCreator, resolves
characters: a library character through the `characters` tool (only approved
package content is canon, never a draft or archive), otherwise an identity
already held, else a bounded name-only lookup in the caller's own workspace
(ambiguity goes back as a question). Never scan the home directory or invent a
character because a file is missing; an unspecified character is not "no
character". Resolved roots and private asset names never enter a public
proposal, form or report. A missing pose becomes a missing-only request through
image-creator's mascot leaf, preserving the approved identity. Script text goes
through Writer's `write-script` family, never composed by the Assistant or
Creator; grounding through researcher; narration through audio-creator.
VideoCreator returns a dependency request, released as its own approved unit.

**Lifecycle.** `propose` returns `pending-inputs` or `awaiting-approval` with
the proposal SHA-256; missing inputs are described in `spec.pending`, never
invented files or hashes. Only a matching `render` against the approved preview
hash releases the final video. Nothing self-approves; frozen projects and
delivered outputs are never rewritten.

**References.** HyperFrames plans use the external references ("Video
authoring references"); Motion Canvas plans only their own local one.

**Motion Canvas runtime.** The maintainer provisions it with
`engines/motion-canvas/setup.mjs`; jobs never install or upgrade it. Setup
clones a browser into ignored `runtime/browser/` and never copies cookies or a
profile; rerunning it never overwrites a different clone or changed lock. Every preview records the actual
runtime/Node/browser identity; a change needs a fresh preview and approval.
Scenes are trusted authored code, not a hostile-JavaScript sandbox. Reactive
bindings use the view's `globalTime` signal, not generator-only `useTime()`. On
HyperFrames, the mouth track declares a function the scene calls (inline scripts
are coalesced after external files) and each cue boundary writes each mouth
once, to avoid reverse-seek ordering conflicts.

Final QA carries the engine's contrast-audit status; Motion Canvas has none and
reports "requires manual visual review".

## Promotion family

`video-creator-pipeline/create/promotion/` serves `create-promotion`:
authored promotion video — launch/promo, brand or sizzle pieces, feature
reveals, kinetic typography, logo stings — that VideoCreator designs and draws
itself in HTML/CSS/SVG/GSAP, optionally matching a local reference video.
Always `kind="work"`; free. No other served leaf fits a launch/promo piece (ad needs approved assets and a CTA, tour is a UI walkthrough, explainer
a learning goal).

**Structure approval, free look.** The approval covers structure only — beats,
timing, verbatim copy, seams, audio plan and the look in words — never pixel
sizes. The look is an explicit gap-driven improve loop against the reference
and the leaf's `<Standard>`, fixed by redesign. Why:
[decisions/explainer-structure-approval.md](../decisions/explainer-structure-approval.md).

**Storyboard vocabulary.** The storyboard decides the film's taste, not the
implementer, so Round A names entries of the kernel's
`references/motion-vocabulary.md` (names, looks and usual builds, no rules)
instead of generic "fade" or "card". Keep the vocabulary rule-free:
[decisions/storyboard-vocabulary-rule-free.md](../decisions/storyboard-vocabulary-rule-free.md).

**Lifecycle.** Round A writes `storyboard.md`; `promotion.py propose` stores it
with its SHA-256. One Assistant-relayed approval releases authoring, drafts and
the final; the final render verifies the hash and encoded output and records a
source tree hash, never freezes a copy.

**Dependencies.** VideoCreator has no image generation, TTS, music or SFX: the
storyboard's audio plan is the brief the Assistant gives audio-creator and
rasters go through image-creator, each its own released unit. Reproducing a
third-party brand needs the client's permitted-use statement relayed in `note`.

**PV and series.** A PV or showcase reel of a store, site, product or event is
this leaf, not a separate subject: the supplied photos, page stills and footage
are the picture and every on-screen fact comes from that material. A series
episode names the approved earlier episode in `series_of`, shares its look and
ending, starts from a copy of its source and gets its own storyboard approval.
A model-generated PV is not served.

**Knowledge.** The pinned references and motion vocabulary ("Video authoring
references"); create-promotion alone may also use cut-the-curve's seam
techniques.

## Story family

`video-creator-pipeline/create/story/` serves `create-story`: a short character
story in which recurring characters from their approved art act out a narrative
across scenes, with dialogue from an approved script and a finished soundtrack,
staged as 2.5D HyperFrames animation (frame rate: "Frame rate"). Always
`kind="work"`; free. It is not a learning explainer with a presenter
(create-explainer-video), a piece presenting a subject (create-promotion) or a
generated MV.

**Why authored, not generated.** Generated video redraws a character on every
shot and drifts from its approved design, and a generated clip has no shared
clock with separately synthesised speech, so lip sync cannot be aligned. The
leaf uses the cast's approved art byte for byte and stages speech with poses,
expressions and timing; it never claims lip sync. Generated shots may appear
only as footage inserts without a cast member.

**Lifecycle.** The same structure-approval and free-look loop as
create-promotion, with a `## Cast` and a beats table whose dialogue column
quotes lines verbatim. `story.py propose` checks cast, speakers and quoted
lines against the supplied art and the approved script (a mascot pack counts
only its manifest's passed items), then appends their SHA-256 so the one
approval hash binds them. `story.py render` reuses create-promotion's checks
and also requires every cast member's bound bytes to be referenced. Script,
missing poses and voices/music/SFX (speech per line, then one Mix) are
separate units the Assistant releases.

## Master family

`video-creator-pipeline/create/master/` serves `create-master`: one finished
delivery master from already-approved parts — silent segments joined by cut or
dissolve, a finished WAV or audio-creator Mix bundle under them, optional
captions burned in plus an SRT sidecar. Always `kind="work"`; free. It covers
the finishing that generate-music-video's supplied mode, several generated clips
or cut promotion pieces need, before legacy `creator-media-assembly`, which
keeps overlays on footage, segments' own sound, ducking and edit-spec trims.

It decides nothing creative and has no proposal round: every part is already
approved and the form is the spec; a missing decision is `Q<n>:`. Segments must
be 8-bit SDR (converting HDR would grade it) and share size and frame rate, and
the soundtrack must last the joined picture within one frame. A mismatch is a
dependency request for `edit-clip` or audio-creator; this leaf never trims,
pads, stretches, reframes or retimes a part. Segment sound is dropped.

- Picture is joined in one H.264 encode. The installed ffmpeg has no subtitle
  or text filter, so burned-in captions are drawn first by the `hyperframes`
  CLI as a transparent layer and composited inside that same encode; the
  picture never passes through the browser.
- A Mix bundle is verified by AudioCreator's own `verify_bundle` and used from
  re-validated byte copies, never its mutable paths; its captions are the
  default source and the final true peak is checked against its approved
  ceiling (a plain WAV must stay below 0 dBTP).
- Decode and canvas/fps/duration/audio checks run before publication; a FAIL
  publishes nothing. Sync, listening and caption reading speed stay unverified.

## Clip family

`video-creator-pipeline/<verb>/clip/` is one short shot, not a generic
film-production workflow. Clip does not consult the HyperFrames references, and
no external menu/router is pulled in.

- `generate-clip`: silent single-shot MP4 from text or one starting image and
  one appearance reference. The allowance counts failures. Pixel is an
  aesthetic, not a proven sprite grid.
- `edit-clip`: trim/contain-or-cover/mute/encode one segment. GIF never silently changes size/fps and
  never promises a seamless loop; an original odd-sized clip is padded up, not
  cropped down.
- `analyze-clip`: findings on one clip, no new video. Original-file metrics,
  sample frames and optional whole-clip analysis are separate evidence sources;
  frame times are seek positions, not exact decoded PTS.

`free` means zero media-generation calls, not zero reasoning/analysis cost.
xAI persistent public storage is disabled in this profile
(`video_gen.xai.storage.enabled: false`): never turn it on, since generated
media would become public; localize temporary URLs immediately.
Uploading an input image (`upload_inputs`) and remote video analysis
(`remote_analysis`) need separate consent; without it, review is local and
sampled, with temporal/audio quality unverified. No create-clip/source-clip
leaf is invented: authored motion and licensed stock sourcing are separate
families. Video analysis runs through the `video-analyze-mimo` tool override;
its tests invoke the handler with real imports so a registration-only test
cannot hide a deferred ImportError.

A failed served clip is a finding, never a silent fallback to the legacy
technic. To withdraw the route, remove the video-creator peer, external skill
root and served-clip routing together and restart the single gateway.

## Pixel-animation family

`video-creator-pipeline/create/pixel-animation/` carries one verb.
`create-pixel-animation` delivers a grid-exact pixel animation (sprite/cel
cycle, loop, effect, integer-step parallax) as an RGB-lossless master MP4, a
yuv420p compatibility MP4 and an optional GIF, with palette, cadence and loop
seam verified numerically on the encoded files; nothing is generated by a model
and it is free. A model-made
clip with a pixel look is `generate-clip`, which guarantees no grid. It does
not draw a still from scratch when the still is the deliverable (that is
image-creator's `create-pixel-art`, whose native PNG and `palette.json` may be
this leaf's `source`). Always `kind="work"`; no proposal round.

The leaf's scripts own the flow. Non-obvious rules: encoding is
nearest-neighbour integer scaling only, with the container fps an integer
multiple of the effective fps so every native frame is held equally; contact
sheets use ImageMagick `+append`, never `montage`.
