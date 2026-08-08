# QA contract — media assembly

The orchestrating assistant performs a read-only inspection of the assembled deliverable at its durable path.

## Scope
Inspect the output of a `media-assembly` unit: verified parts combined per a
fixed edit spec (mux, concat, mix, overlay, re-container). This contract
verifies the COMBINATION; each part already passed its own family contract —
do not re-run part-level checks except where assembly could have altered them.

## Required inputs
The assembled file at its durable path, the edit spec (cut list, sync points,
transitions, mix levels, output contract), and the QA-passed part inventory
with durable paths. Missing edit spec or part provenance means the unit was
malformed — say so.

## Checks
1. Measure the output contract with read-only tools (`ffprobe`): container,
   codec, resolution/aspect, duration, streams, size cap, loudness target.
2. Verify part fidelity: every inventoried part appears, in the specified
   order, and no part was altered beyond the edit spec — spot-check a frame /
   audio segment per part against the source part's durable file; a
   regenerated or silently re-cropped part is a defect.
3. Verify the joins: sample every cut/transition boundary (frames around each
   timecode) for glitches, duplicated/dropped frames, and the specified
   transition type/duration; check the loop wrap when the spec names one.
4. Verify sync: voice-to-scene alignment at the named sync points
   (transcribe a segment and check timing against the spec); music
   ducking/fades where specified; captions/overlays at their timecodes.
5. Record itemized evidence (timecode, measured value, part id) in the
   verdict/feedback.

## Not verified / never do
An unreadable output, a missing edit spec, or a part not in the QA-passed
inventory means NOT verified — obtain what is missing or say plainly it cannot
be checked. Defects route to the assembly unit only when the JOIN is wrong; a
defective part routes to its family unit. Never re-edit, re-encode, or repair
the file yourself.
