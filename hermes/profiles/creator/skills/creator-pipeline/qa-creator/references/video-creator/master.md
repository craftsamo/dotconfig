# Quality assurance — video-creator: master

Read [common quality assurance](../../SKILL.md) first.

Check the master against the form, not against taste: segments in the
given order, the requested cut or dissolve at every join with no black or
frozen frame (the `join-<k>.png` sheets), the soundtrack present from the
first frame to the last, and captions verbatim, readable at the size of
use and not covering text already in the picture. The helper's PASS covers
canvas, fps, duration, audio presence, full decode and true peak (against
the Mix ceiling when a bundle was used); sync, listening and caption
reading speed stay unverified until a human watches it. A part that looks
wrong is a finding against that part's own leaf, not something this leaf
repairs.

The look-before-you-answer numbered steps and the verdict/delivery shape are
common — see [common quality assurance](../../SKILL.md).
