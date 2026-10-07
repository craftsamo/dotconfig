# Commission — video-creator: promotion

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| authored motion design: a launch/promo, brand or sizzle piece, feature reveal, kinetic typography or logo sting that the hands draw in HTML/CSS/SVG/GSAP, including "reproduce / make one like this" from a motion-graphics reference; also a PV/showcase reel of a store, site, product or event built on its supplied photos, page stills or footage, and the next episode of such a series (`series_of`) | `create-promotion` | free, 3..60 seconds, 24/25/30/50/60fps (default 30, or a reference's nearest rate), 16:9 default / 9:16 / 1:1 / 4:5; always kind="work"; storyboard + hash first, approval releases authoring/drafts/final; music/SFX/voice/raster assets are separate audio-creator/image-creator units scored to the approved storyboard; third-party reproduction needs the user's permitted-use statement |

Ad means a specific audience, promise and intended action. PV primarily
introduces qualities/experience/world: neither duration nor a CTA alone decides.
A PV authored from supplied material is create-promotion. A generated ad is
not a leaf of its own: its picture is text-free generate-clip shots, and
create-ad then composes them as supplied muted footage with the exact copy,
claims, product/logo rasters, CTA and audio. A model-generated PV is not
implemented. Never silently route a requested generated ad or PV to MV.

## Choosing and filling

`create-promotion` is the served route for authored motion design: a launch or
promo piece, brand/sizzle video, feature reveal, kinetic typography or logo
sting that VideoCreator designs and draws itself in HTML/CSS/SVG/GSAP,
3..60 seconds at 24/25/30/50/60fps (16:9 default, 9:16, 1:1, 4:5). It is not a
UI task walkthrough
([create-tour](tour.md)), a CTA/claims advertisement from approved assets
([create-ad](ad.md)), a learning explainer
([create-explainer-video](explainer-video.md)) or model-generated footage
([generate-clip](clip.md) / [generate-music-video](music-video.md)).
"Reproduce this video" / "make one like this" with a motion-graphics
reference is this leaf with `reference_use: reproduce` or `inspiration`.
A PV or showcase reel that introduces a store, site, product or event
through its own photos, page stills or footage is this leaf too, with that
material as `assets`; its facts (items, prices, hours, claims) come only
from the material or the user. A series (one reel per store) is one
approved first episode, then one form per store with `series_of` pointing
at the approved episode's directory: each episode shares the series' look
and ending, opens on its own material, and gets its own storyboard
approval.

Settle with the user only what changes the piece: `subject`, `what_for`
(purpose, destination, viewer), aspect/duration/fps if not obvious (fps
defaults to 30; with a reference, VideoCreator proposes the reference's
nearest allowed rate, e.g. 60 for a 59.94/60fps film), any exact
copy they fix, supplied assets, and the look/energy in their words. Do not
ask the user for a storyboard, a shot list or timings: VideoCreator
proposes them. A reference video is read locally; it never authorizes an
upload. The storyboard the user approves is the structure (beats,
timing, copy, seams, audio plan); the look is iterated after approval, so
do not ask the user to sign off pixel sizes. Reproducing a third-party brand, logo or copy needs the user's
permitted-use statement (for example "internal study, not published"),
relayed verbatim in `note`; without it, the form says `inspiration`.

Plan the dependencies up front. VideoCreator draws vectors and UI itself but
has no image generation, TTS, music or SFX. Tell the user the expected
units: the storyboard approval, then audio-creator's soundtrack (music
and/or SFX, usually a Mix master) scored to the approved storyboard's audio
plan, then any raster asset the storyboard lists as pending through the
fitting image-creator leaf. Each is its own released unit with its own
budget/approval; generating them does not ride on the storyboard approval.
A piece the user wants silent is `audio: none` in the storyboard, stated,
not assumed.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-promotion` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; storyboard, authoring/drafts and final render are not one-reply work |

## Round-trip and approvals

Keep every round in one specialist work conversation. Round A returns
`proposal-v<N>/storyboard.md`, its SHA-256, a status and a pending list. Show
the user the storyboard itself (beats, copy, design, motion language, audio
plan) for approval; never approve on the user's behalf and never
recompute a hash for changed bytes. After approval send `approved_plan` +
`approval_sha256` in the same conversation: that releases authoring, draft
renders and — once pending items are resolved — the final render.

For each pending id, release its producer as its own unit and return the
finished file into the same video conversation:

- `audio`: brief audio-creator from the storyboard's `## Audio plan`
  (tempo, energy curve, drop and hit times in seconds, SFX list with times,
  exact duration). Usual path: generate-music or create-music for the bed,
  create-sfx/generate-sfx for hits, then create-mix to place them on the
  storyboard's timeline and return one master WAV. Hand VideoCreator the
  master path; it places it and resolves `audio` in its inputs file.
- `image:<name>`: the fitting image-creator leaf with the storyboard's exact
  spec (subject, size, background/alpha, style). Never ask VideoCreator to
  generate it.

The storyboard approval covers structure: beats, timing, verbatim copy,
seams and the audio plan, with the look described in words. It does not fix
sizes or layout. After approval the hands iterate the look against the
reference as far as the drafts show is needed — redrawing, resizing or
restyling a scene needs no new approval. Changed beats, copy, duration,
aspect or audio plan need a new numbered storyboard and a new approval.
When relaying a brief with a reference, pass what the user said about it
verbatim and let the hands analyse the reference; do not replace it with
your own summary.

For a series episode, send `series_of` as the approved earlier episode's
delivery directory (its `proposal-vN/` and final render) and this
subject's own material as `assets`; never ask the hands to reuse an
earlier episode's storyboard approval.
