# Plan — video-creator: music-video

Read [common plan](../index.md) first.

## Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for MV: the same 2 + 1 attempt ceiling as clip, but proposal approval is
required before spending; failed attempts count against that ceiling too.

## MV: a concrete world and performance, then approval

Use generate-music-video for a short model-generated music-video-style piece ("MV"), not a
single-shot hero, UI tour, full song or an edit of existing footage. Subject
(character or otherwise) is a form value, never a new character-mv leaf.
Fill subject/theme/style, direction (performance by default), music_mode and
remote_analysis. Infer optional performance/theme_detail rather than asking
the client to write a storyboard. Style is rendering, theme is space/materials/
light, direction is staging emphasis. Read the selected leaf references; theme
defaults are concrete starting points overridden by theme_detail/must_keep.
New proposals default pace to steady and transition to cut only when shots
change. For "sluggish" feedback, first identify what the reference actually
does: body action, camera travel, lens occlusion, cut or hold. Do not replace
a spatial wipe/zoom-through with snappy + cut merely because it sounds faster.
Offer snappy + cut only when crisp edited boundaries are the intended change.
Preserve separately described speeds (slow performer, fast cuts); do not
equate pace with BPM or turn performance into mandatory rapid editing.
Continuous forbids shot breaks regardless of pace. If that conflicts with an
explicit cut-montage request, resolve the conflict before approval. Optional
fields need not become extra interview questions when intent is already clear.
Have the hands put tempo/boundary choices in the proposal AND actual prompt.
For reference-led spatial motion, read the MV leaf's spatial-direction.md and
retain camera/actor/object motion separately. Each critical action gets START /
CROSS / AFTER in plain prose: position/shape/destination, visible passage, then
what remains in view. A keyhole seen is not a keyhole entered. Confirm priority
and evidence expectations, not just motifs or the word fast. Do not demand that
the client write this breakdown; the hands propose it from permitted evidence.
An isolated 5-second aperture trial showed passage-like evidence but wrong
opening shape; its 15-second integrated counterpart did not preserve the
passage. Treat this as risk evidence, not a guaranteed prompt recipe. If needed,
offer a separately budgeted generate-clip isolation or a scoped production plan;
never silently fan out one MV allowance into several shot generations.
Keep the detailed proposal separate from a compact prompt-only file. Before
approval require its measured 1..1800 UTF-8 byte count and SHA-256; a long
storyboard/reference dump cannot become the tool argument. The shared-route
budget accounts for the observed FAL 2048-byte rejection as well as xAI's
reported 4096 limit. Compression preserves mandatory direction; it never
silently drops client requirements or restores spent attempts.
Keep the action relationships in that compact prompt; remove redundant visual
adjectives first. If required relationships cannot fit, resolve scope before spend.
Free text is first-class, not a nearest-preset lookup. Known recipes are not
yet live-render guarantees. Theater can be red/black/white playing cards OR
ice-blue/silver crystals: do not keep velvet/gold when the client replaces it.

Explain sound modes before handoff: generated requires current native-audio
support (the current xAI-first chain does not advertise it, so do not offer
generated sound as working today); supplied takes music_file before generation
but permits a music_plan description in the initial zero-spend proposal.
That preliminary proposal is pending-inputs, can_generate: false; it records
the intended producer/spec/duration and separate music/finishing order, never
an invented audio file/hash. Obtain the music production release separately,
then hand off the real file for a new numbered video proposal/hash and its
approval. Pending image-upload consent likewise does not prevent zero-upload
planning. Never turn preliminary approval into generation permission or
ask the client to choose the accepted concept again. Supplied produces a silent visual master for a
separately released finishing job; silent is an explicitly silent MV-style
piece. VideoCreator never uploads reference_video/music_file or generates a
standalone song. An exact lyric/beat/lip-sync requirement is unsupported, not
an optional note to ignore. Exact lettering needs a text-free generated base
and a known, approved finishing route. Do not spend on a base whose required
finish has no agreed route. Never interpret a MiniMax mention as permission
to change the profile's xAI-first generation chain. With a character reference,
default to 10s: xAI clamps that mode to 10 even though its general schema says
15. An explicit longer request needs a decision before approval, not a paid
attempt followed by a shorter delivery.

Character-image upload consent and generated-video remote-analysis consent
are distinct, as for clip. Reference videos are local samples or a client's
description, not direct video_generate inputs. Local-only inspection must
stay local; a file path is not consent to remote image/video analysis.

The first handoff has NO approved_plan or approval_sha256. It returns a
proposal, not a movie, and spends zero media-generation/remote-analysis calls.
Show its expanded theme, short beat progression, actual generator freedom,
must_keep/finishing split, sound mode, backend limits and allowance. A human
approves with clarify; an assistant receives the proposal plus a text approval
question. Only explicit approval authorizes the second round in
[build](../../build/video-creator/music-video.md). Prior approval to explore or
a budget line alone does not release generation.
Pace/transition changes require a new proposal and approval; the allowance
already consumed remains consumed. Existing approved proposals without these
fields keep their frozen timing/prompt, not the new defaults.
