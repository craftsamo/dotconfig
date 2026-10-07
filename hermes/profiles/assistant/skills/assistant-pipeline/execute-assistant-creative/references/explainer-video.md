# Commission — video-creator: explainer-video

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a bounded local-authored explanation of a topic for an audience with a learning_goal | `create-explainer-video` | free, 1..180 seconds, always kind="work"; explicit v1 HyperFrames or v2 Motion Canvas render (never a silent switch; an old v1 Motion Canvas discussion-only proposal needs a fresh v2 proposal and approval), 16:9 (1280x720)/9:16 (720x1280), HyperFrames at 24/25/30/50/60fps (default 30), Motion Canvas 30fps only; framing none/bust/full separate from performance still/puppet/animated and lip_sync off/cues/baked; missing character/script/grounding/audio inputs return as dependency requests, never invented; propose/freeze/snapshot/render mirrors Tour/Ad's proposal-then-approval shape |

create-tour, create-ad and HyperFrames create-explainer-video
support opt-in graphics: three-webgl2 through their local Three graphics
contract, not a separate subject. you select it for actual depth or GLSL
surface requirements and verifies provisioning; no silent flat substitute.
It uses one procedural WebGL2 layer with pinned local Three/CLI/browser and
GSAP time. Addons, async asset loading, WebGPU and Motion Canvas combinations
remain outside that scope. Existing exact proposals and previews still apply.

## Choosing and filling

### Explainer video: scope, framing and dependencies

`create-explainer-video` is for a topic explained to an audience toward a
learning_goal — never a UI task walkthrough ([create-tour](tour.md)), an
advertisement ([create-ad](ad.md)), or a model-generated music-video-style piece
([generate-music-video](music-video.md)). Always `specialist_call(kind="work")` even
though it is free (local authoring only, no provider fee; 1..180 seconds,
16:9/1280x720 or 9:16/720x1280; HyperFrames at 24/25/30/50/60fps, default
30; Motion Canvas 30fps only). `framing`
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
gap until a separate method is approved; do not ask the user to write cue
JSON or assume generate-speech supplies it.

Character is not implicitly "none": ask whether it is none, an existing
character or a new one before filling the form. An existing character
missing a pose needed for this explanation is a missing-only-pose
generation request through the fitting image-creator mascot leaf,
preserving the approved anchor identity, never a fresh character concept.
New character art routes through image-creator's mascot family, script
text through Writer's `write-script` leaf (never you composing the script
yourself), grounding facts through researcher as needed, and narration/audio
through audio-creator — each is its own separately released, separately
budgeted/approved unit, sequenced the same way as any other composite request
([commissioning](../SKILL.md)).
VideoCreator never calls those hands/peers directly; a form that needs
one comes back to you as a dependency request, not a `no skill fits`.

A character from the library resolves through the `characters` tool:
`list`, then `show <slug>` for the character card (profile, primary assets,
voice ids), then `show <slug> visual` / `animation` / `voice` for that
medium's guide and approved files. Carry the profile's identity core and
boundaries into the form; drafts and archive are never canon. Any other
workspace/asset root and private asset names are
yours to resolve, never VideoCreator's: prefer a direct path or an
identity you already hold, else a bounded name-only lookup inside your
own known workspace; an ambiguous match is a question to the user,
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

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-explainer-video` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; the propose/freeze/snapshot/render rounds and any dependency-request round-trip are not one-reply work |

## Round-trip and approvals

For `create-explainer-video`, keep the propose/freeze/snapshot/render turns
in one specialist work conversation the same way as
[create-tour](tour.md). Relay
`propose`'s `pending-inputs`/`awaiting-approval` result and show the user its
proposal SHA-256 for approval before anything else; never invent a file or
hash for an input the spec marked pending. A dependency request the hands
return (missing character art, script, grounding, or narration) is a
finding for you to release as its own separately budgeted/approved unit
through image-creator/writer/researcher/audio-creator — never something
VideoCreator fetches itself, and never a reason to relax framing/
performance/lip_sync to something less than what was asked. The proposal
also fixes an explicit v1 HyperFrames or v2 Motion Canvas renderer; changing
it needs a new proposal too, never a silent switch, and an old v1 Motion
Canvas discussion-only proposal cannot be resumed as a render — only a
fresh v2 proposal and approval can. Only a
matching `approved_plan`+`approval_sha256` releases `freeze`, and only a
matching `approved_preview`+`approval_sha256` releases `render`; a changed
topic/audience/learning_goal or framing/performance/lip_sync choice needs
a new proposal, never a render against stale approval text. Never resolve
or relay your private asset root/name in the handoff text beyond
what the leaf's form actually needs.
