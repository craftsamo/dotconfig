# Plan — video-creator: explainer-video

Read [common plan](../index.md) first.

## Explainer video: scope, framing and dependencies

`create-explainer-video` is for a topic explained to an audience toward a
learning_goal — never a UI task walkthrough ([create-tour](tour.md)), an
advertisement ([create-ad](ad.md)), or a model-generated music-video-style piece
([generate-music-video](music-video.md)). Always `specialist_call(kind="work")` even
though it is free (local authoring only, no provider fee; 1..180 seconds,
16:9/1280x720 or 9:16/720x1280 at 30fps). `framing`
(none/bust/full) is independent of `performance` (still/puppet/animated)
and `lip_sync` (off/cues/baked): bust only proposes lip-sync cues, never
substitutes for an explicit `off`; full supports whatever performance was
actually approved, never an automatic upgrade past it. Renderer is an
explicit engine choice made and preserved in the proposal, never a silent
switch: v1 HyperFrames suits HTML/UI or media-oriented compositions, v2
Motion Canvas suits reactive diagrams, algorithms and Canvas-based
explanation — it needs no external HyperFrames skills, using its own
local reference inside the leaf instead. An old v1 Motion Canvas
discussion-only proposal stays non-executable and needs a fresh v2
proposal and a new approval, never reuse of its old hash. Neither renderer
infers phonemes/visemes, authors a rig, or plays a native talking model:
a naturally talking video is not something this leaf generates on its
own. Already-authored cue JSON plus mouth PNGs, or a supplied finished
muted MP4 carrying its own sync evidence, may drive the performance
instead; a required performance asset that is missing is a pending-inputs
finding, never a silently lesser framing/performance/lip_sync. No current
hands leaf automatically produces reviewed mouth cues. Report that capability
gap until a separate method is approved; do not ask the client to write cue
JSON or assume generate-speech supplies it.

Character is not implicitly "none": clarify none vs. an existing
character vs. a new one before filling the form. An existing character
missing a pose needed for this explanation is a missing-only-pose
generation request through the fitting image-creator mascot leaf,
preserving the approved anchor identity, never a fresh character concept.
New character art routes through image-creator's mascot family, script
text through Writer's `write-script` leaf (never the retired writer
technic, and never Creator composing the script itself), grounding facts
through researcher as needed, and narration/audio through audio-creator —
each is its own separately released, separately budgeted/approved unit,
sequenced the same way as any other composite request
([common build](../../build/index.md)).
VideoCreator never calls those hands/peers directly; a form that needs
one comes back to you as a dependency request, not a `no skill fits`.

The caller-selected workspace/asset root and any private asset names are
yours to resolve, never VideoCreator's: prefer a direct path or an
identity you already hold, else a bounded name-only lookup inside the
caller's own known workspace; an ambiguous match is a `Q<n>:`/`clarify`,
never a guess, and never a broad scan of the whole home directory.
Explicit assets are retained as unchanged originals. Concrete input paths may
travel in private job forms/specs for execution, never in public repository
files, examples or exports. Use neutral staged asset names; private proposals
are not automatically public-safe documents. Its lifecycle mirrors Tour/Ad's
proposal-then-approval shape:
`propose` writes `plan.json`/`proposal.md`/an assets snapshot and returns
`pending-inputs` or `awaiting-approval` with the proposal's SHA-256 —
unresolved inputs are named in `spec.pending`, never invented as files or
hashes. Only `approved_plan`+`approval_sha256` releases `freeze`, and
only a matching `approved_preview`+`approval_sha256` releases `render`;
never self-approve, and a frozen project or delivered output is never
rewritten in place.
