# Motion Review

Reviewing motion honestly means examining more than a single comfortable
sample point. A move can look fine at its midpoint and still fail at its
start or its end — an abrupt launch, an overshoot that never settles, a
snap at the very last frame — so any review must check the sustained holds
of a shot as well as its first and last frames, not just a spot in the
middle. Small or fast actions need denser sampling still: a quick gesture, a
flash transition, or a rapid state change can fall entirely between samples
taken every second or two and be missed altogether, even though it is
clearly visible at normal playback speed.

## Use the actual delivered timestamps, not the authored ones

When reporting or reasoning about when something happens in a rendered
piece, use the real presentation timestamps (PTS) of the actual delivered
file, not the nominal timecodes from the authoring timeline. Renders can
drift, get trimmed, or reflow during export or re-encoding, so a timestamp
correct in the source project file is not guaranteed to still be correct in
what was actually delivered. Extract frames or note timing from the file
that will actually be watched, and label the timestamps as coming from that
file.

## Stills cannot substitute for playback

Perceived smoothness, correct easing, and overall timing quality are
properties of motion in time — they cannot be fully judged from any number
of still frames, however well chosen. A still frame review can validate
composition, color, and the presence/absence of a pose, but a stutter, a
mistimed ease, or a motion that is technically present in the frames yet
reads as wrong at real speed will not show up in stills. Distinguish
explicitly, in any review report, between what was checked via frames and
what was checked via actual playback at normal speed, and do not let a
frame-based check stand in for a playback-based conclusion.

## Never claim continuous review that did not happen

Report exactly what was examined: which specific timestamps, how many
samples, whether playback at real speed occurred, and over what portion of
the piece. Do not describe a review as having "watched the whole video" or
similar language implying continuous playback review if the actual method
was sampling frames or stills at intervals. An accurate, scoped report of
partial review is more useful and more honest than an inflated claim of full
coverage.

## Cases

**Revision — single mid-point still.** Request: a 3-second logo animation is
approved for delivery based on a single screenshot taken at t=1.5s, roughly
the midpoint. Weak observation: the delivered file has a jarring overshoot-
and-snap at its very last frame (t≈2.9s) where the logo overshoots its
final scale and never settles smoothly. Cause: only one frame, at the
midpoint, was checked — the boundary frames where the actual defect existed
were never examined. Revision: extract and inspect the first and last
frames of the animation in addition to several samples across the full
duration, or watch the clip at real speed, before approving.

**Revision — timeline time instead of real PTS.** Request: a review report
states the video was checked "at t=0:12 and t=0:34" for motion issues, using
timecodes copied from the authoring project's timeline. Weak observation:
those timestamps do not correspond to the same moments in the actual
delivered file, because a re-encode step shifted timing by roughly 120ms and
trimmed a few frames from the head. Cause: the report used the authored
timeline's nominal timecodes rather than the real presentation timestamps of
the file that will actually be watched. Revision: re-extract frames from the
real delivered file at its own PTS values, and label reported timestamps
explicitly as coming from that specific rendered file.

**Retain — accurately scoped partial review.** Request/observation: a review
report states plainly, "checked composition and color via three still
frames; motion smoothness and full-duration timing were not evaluated,
playback review still pending," and someone flags this as an incomplete
report needing expansion before it can be accepted. Evidence for retaining
it as-is: the report accurately describes exactly what was and was not
checked, with no overstated claim of coverage. That honest partial-review
report is the correct artifact at this stage of the process; the fix needed
is scheduling the pending playback review, not rewriting the report to
sound more complete than the work that was actually done.
