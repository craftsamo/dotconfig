# Spatial Direction

When this applies: a reference_video/source-grounded recreation, or any
request naming camera traversal, occlusion, or depth (passing through a
gap, a lens/pupil/keyhole transition, walking past an object, entering a
world). Inspect the consented source or the client's description before
writing beats; preserve what actually changes across the shot, not a
theme's abstracted motif. Not a new form field or a template registry -
this governs how Step 4 writes tempo/progression prose for such requests.

Motion bookkeeping: separate camera motion, actor motion and object motion
in the prose; state which one is doing the traversal. Track near/far scale
change, what fills the frame at the closest point, and what the moving camera
or actor exits into. A lens-occlusion, camera dive through a pupil or keyhole
transition is a specific observed/requested action, not interchangeable with a generic
hard cut or the nearest theme preset; keep its own material and geometry
even when a theme reference is also loaded.

## Writing the critical-action prose

For each critical action write three short beats, not a fixed shot list:

- START: camera still outside the threshold; the opening's shape and a
  hint of the destination are visible through it.
- CROSS: forward progression through the opening; its rim expands past the
  frame edges, and any inner thickness or sidewalls are seen passing by.
  This is not a pushback, a flat zoom, or a static hold.
- AFTER: the original threshold is out of frame behind the camera; the
  camera is surrounded by the destination space, with continued parallax
  into it.

Occlusion by a foreground object (curtain, skirt, card): write the object
filling the lens first, then the next view revealing with a stated
direction (up, aside, forward) - not an unexplained straight cut between
two disconnected views.

On-screen letters as a foreground occlusion: write a letter's stroke
cropping the frame edge with the subject glimpsed through the gap between
strokes, not a fully readable word treated as a billboard behind the
subject.

Keep shape fidelity and passage success as separate claims in the prose
and later in QA. For a real keyhole, specify ONE contiguous opening - a
round top connected to a narrow stem - not a large peephole with a
disconnected small keyhole drawn below it.

## Fitting the approval budget

When trimming the compact prompt to the 1..1800 UTF-8 byte budget (Step 4),
keep the critical action's START/CROSS/AFTER relations and drop ornamental
synonyms elsewhere first, never the action's endpoints. If the critical
action cannot fit while staying exact, or the requested exactness is
unsupported, report the options and stop for a scope decision; never
silently delete the action or spend an extra call to compensate.

## Evidence and verdicts

Record each critical action's evidence separately as one of: shown only,
crossing evidenced, missing evidence, or contradicted - plain prose
labels, not a new machine-readable enum. Every verdict carries its sample
timestamps or filenames. Object presence alone, or a full technical
decode, is not passage evidence. A blended/superposed view does not prove
crossing; if the original threshold is not absent from frame and there is
no sustained destination-interior view, record no pass. Dense sampled
frames support a transition claim but cannot certify exact 3D motion.
Evaluate native shape fidelity separately from passage, and say plainly
where an optional aesthetic passed while the primary action failed.
Sparse global frames (roughly 3 across the whole clip) are inadequate
evidence for one short critical event; say so rather than passing it.

Bounded optional local inspection, only where local/native image review
is allowed: at most TWO selected critical windows per candidate, each up
to 2s at 12fps (max 24 frames), one contact-sheet look per window with an
immediate qa.md append before the next look. Choose windows from evidence
already gathered; do not keep expanding the search. The exact extraction
command lives in the main SKILL (Step 9); do not duplicate CLI here.
Existing remote_analysis consent limits are unchanged; sampled frames are
never a claim of having reviewed the whole clip.

Empirical note (2026-09-07): a short single-beat prompt produced an
expanding rim and sustained interior view but a wrong-shaped opening
(large peephole plus a separate small keyhole); a longer multi-beat
prompt with explicit start/cross/after wording produced a closer opening
shape but no demonstrated crossing, with beats overlapping. One call
each, unequal duration/complexity, no retries - isolated sample evidence,
not a controlled comparison or a general claim about what any model can
or cannot do. Stronger evidence comes from narrowing scope to verify one
critical action, not from adding more descriptive adjectives. Never
fabricate a percent-complete figure.

## When a critical action keeps failing

If integrated attempts render the right objects but the critical action
still fails, report that quality gap plainly and propose either a
separately budgeted isolated-shot attempt or an explicitly approved
different model/input route; do not silently chain additional
generations, assemble clips, or rescale a prior output to paper over it.
The existing generate-clip leaf is the appropriate tool for a
separately-granted single-shot isolation test; generate-music-video itself stays
one tool call producing one whole candidate. No pipeline fork and no
per-character variant skills.
