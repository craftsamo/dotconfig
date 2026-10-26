
# Pace: Snappy

Intent: pace sets the accent of action and camera, how long a pose or shot
holds, and - only when the clip is multi-shot - the edit rhythm between
those shots. It does not choose transition type, imply a target BPM, or
authorize post-render speedup; those are separate decisions. Snappy means
sharp, accented action - a step, turn or arm gesture that lands with a
clear hit - paired with short camera arrivals: the camera settles quickly,
holds for a visual beat, then moves on. Any ending hold is very short (an
approximate planning range of 0.3-0.7s, not a guaranteed timing), and this
pace does not by itself mandate cuts when transition is continuous.

Prompt guidance: "<subject> delivers <action> as a sharp accented beat -
a quick step, turn or gesture that lands cleanly - the camera arriving fast
on <framing>, holding just long enough to register the beat before moving
on; the final beat settles briefly and ends without lingering." Rewrite the
action and framing around the actual brief; keep the sentence shape, not
the exact words.

Avoid: do not use snappy pace to imply a shot break or cut is required -
under a continuous transition, keep it to accented in-shot action and quick
camera arrivals, not an editorial cut. Do not stretch the ending hold into
a lingering pose; that drifts toward relaxed. If the client's description asks for a
mismatch against the enum (e.g. slow performer with fast cuts), follow the
explicit override instead of forcing snappy defaults.

QA cues: sampled frames can reveal repeated poses or unreadable accents but
cannot certify motion speed or short holds. Use available timecoded temporal
evidence for cadence; otherwise mark it unverified. No exact 0.3-0.7s timing
is guaranteed. Flag blurred or illegible accents rather than calling them sharp.
