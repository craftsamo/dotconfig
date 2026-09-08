
# Pace: Relaxed

Intent: pace sets the accent of action and camera, how long a pose or shot
holds, and - only when the clip is multi-shot - the edit rhythm between
those shots. It does not choose transition type, imply a target BPM, or
authorize post-render speedup; those are separate decisions. Relaxed means
deliberate, legible movement with camera holds long enough to read, and any
pause is motivated by the performance (a breath, a settle, a beat of
stillness before the next action) - not a frozen loop repeating the same
held frame for filler duration.

Prompt guidance: "<subject> moves deliberately through <action>, each
gesture given time to read before the next begins; the camera holds
<framing> long enough to settle on the movement, pausing only where the
performance calls for a breath or a beat of stillness." Rewrite the action,
framing and pause moments around the actual brief; keep the sentence shape,
not the exact words.

Avoid: do not stack this with a snappy/intense cut cadence unless the state
field explicitly asks for a mismatch (e.g. "slow performer, fast cuts") - if
pace and an unrelated cut request conflict without that explicit override,
ask or propose a resolution rather than forcing the nearest enum. Do not
describe a static held frame with no motivated reason; that reads as a
frozen loop, not relaxed pacing.

QA cues: sampled/timecoded frames from the finished clip are the available
evidence - they show whether holds and pauses look motivated at the sampled
points, not a full-duration guarantee of rhythm; a still frame alone never
proves pacing. Flag any hold that looks idle or unmotivated rather than
deliberate.
