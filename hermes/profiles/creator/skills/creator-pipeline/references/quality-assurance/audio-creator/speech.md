# Quality assurance — audio-creator: speech

Read [common quality assurance](../index.md) first.

A speech delivery is never opened with vision; there is no frame to look
at. Read the hands' report against the approved script and the client's
goal: does the readback text match the script, does the take count and
any WARN line still fit what was asked. Never re-run ASR yourself just
to re-score something the hands already measured — that is spending a
fresh take against their tally, not a review. A reproduced seed is
decoded-PCM-hash evidence, not container-byte equality; take the hands'
comparison as given rather than redoing it. Retain every WARN in your
reply exactly as the hands reported it — a WARN is not a defect to
silently drop. The gap between "measured and read back" and "heard"
stays explicit in the verdict: whether that perceptual gap is acceptable
is the client's decision, not yours to resolve by claiming to have
listened.

The verdict and delivery-to-client shape are common — see
[common quality assurance](../index.md); a speech delivery never goes
through the look-before-you-answer vision steps there, per above.
