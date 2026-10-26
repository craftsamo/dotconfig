
# Pace: Intense

Intent: pace sets the accent of action and camera, how long a pose or shot
holds, and - only when the clip is multi-shot - the edit rhythm between
those shots. It does not choose transition type, imply a target BPM, or
authorize post-render speedup; those are separate decisions. Intense means
brief bursts of committed action punctuated by deliberate micro-pauses - a
fast, high-energy feel that stays readable, not strobe-like chaos where the
image is illegible or every frame shows a different body position. Anatomy
and identity must stay coherent through the bursts.

Prompt guidance: "<subject> moves in brief, committed bursts of <action>,
each burst landing with a deliberate micro-pause before the next begins -
fast and high-energy while staying readable, with posture and anatomy
staying coherent throughout." Rewrite the action and bursts around the
actual brief; keep the sentence shape, not the exact words.

Avoid: do not describe motion so fast or fragmented that it reads as
flicker/strobe or unreadable text - each burst needs a legible micro-pause,
not constant unresolved motion. Do not let bursts distort anatomy (extra
limbs, warped proportions) in the name of energy. If the client's description
explicitly asks for a mismatch against the nearest enum, follow that
override and ask/propose rather than forcing intense onto a conflicting
request.

QA cues: sampled/timecoded frames are the available evidence for whether
bursts and micro-pauses stay readable and anatomically coherent - they
cannot certify the full-duration motion never strobes between samples.
Flag any sampled frame with broken anatomy or illegible blur as a defect,
not accepted intensity.
