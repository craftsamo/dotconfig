
# Transition: Continuous

Intent: transition controls boundary grammar - how (or whether) the clip
moves between views - not cut count or motion speed; pace stays an
independent decision. Continuous means no shot breaks, no crossfades, no
dissolves: the entire clip is one unbroken shot. In-shot occlusion (an
object or the subject briefly blocking the camera) and camera movement
(push, pan, orbit) are allowed and can imply a change of vantage without
ever breaking the shot.

Prompt guidance: "The camera stays in one continuous unbroken shot
throughout - no cuts, crossfades or dissolves; any change of vantage comes
from camera movement or a brief in-shot occlusion, not a shot break."
Rewrite the movement/occlusion detail around the actual brief; keep the
sentence shape, not the exact words.

Avoid: if the requested direction (e.g. a montage with a real setup/
development/payoff arc) actually needs distinct cuts to work, resolve that
conflict with the client before approval - do not silently swap continuous
for cut/dissolve behavior to make the montage work. Do not describe a
crossfade or dissolve as part of a "continuous" boundary; those belong to
the dissolve transition, not this one.

QA cues: sampled/timecoded frames may expose an obvious hard cut or
dissolve artifact; full decode proves file integrity, not an unbroken shot.
A still frame alone never proves shot continuity
across the whole duration. Flag any detected cut, crossfade or dissolve as
a mismatch with an approved continuous transition.
For a pass through an opening, follow [spatial direction](../spatial-direction.md): verify approach,
boundary crossing and a sustained inside view, not just an object appearing.
