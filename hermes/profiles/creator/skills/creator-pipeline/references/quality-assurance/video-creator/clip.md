# Quality assurance — video-creator: clip

Read [common quality assurance](../index.md) first.

For clips, use the hands' sampled sheet and a native frame instead of
passing an MP4 to image vision. Read its timecoded video-analysis findings
against the requested motion and client intent. A poster cannot establish
motion, continuity, audio or loop quality. If remote analysis was declined
or failed, carry the temporal QA gap through; acceptance as an unverified
candidate is the client's decision, not an implicit pass. Do not upload
again just to repeat the hands' check. An analyze-clip report is findings,
not a new deliverable: review the evidence and return it without requiring
an output video or opening a new generation job.
For a deterministic clip edit, helper dimensions/duration/decode results
and the bounded framing looks are the checks. Do not expand sampled QA
into pixel-exact source alignment/padding calculations or ask the hands
to run extra approval-gated scripts. Carry unverified checks explicitly.

## Reference-led spatial actions (shared video review)

This section is the shared video review for reference-led spatial motion —
[music-video.md](music-video.md) links here rather than repeating it.

For reference-led spatial actions, read each critical event's START / CROSS /
AFTER evidence and opening/subject shape verdict separately. "The keyhole is
visible" is not "the camera passed through it"; a fade to an interior does not
meet an approved continuous crossing. A correct actor, world and words do not
outweigh a failed critical passage. Do not reuse an isolated-shot success as
evidence for its integrated version. Carry sampled/unknown status honestly;
propose a separately released isolation or revised scope, never automatic
extra shot generation, unapproved montage assembly or unsupported completion %.

The look-before-you-answer numbered steps and the verdict/delivery shape are
common — see [common quality assurance](../index.md).
