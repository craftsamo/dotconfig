# Quality assurance — audio-creator: mix

Read [common quality assurance](../../SKILL.md) first.

A mix delivery is reviewed the same way as [speech](speech.md),
[SFX](sfx.md) and [music](music.md): never opened with vision, never
relistened to. For a proposal round, read
`direction`/`arrangement`/`must_keep` expanded into the actual cue list
(placement, gain, fades, envelope) against what the client asked, and
confirm the approval hash matches the exact proposal text before any
render was released. For a rendered take, read the hands' measured
duration/sample-rate/channel-count/sample-count against the planned
timeline, and the measured peak/true-peak/clipping/integrated LUFS
against any requested `target_lufs` — these are the actual numbers, never
the requested target reported as if measured. An existing input source's
own defect (e.g. a source that already clipped) is retained and reported,
never silently corrected, and a mix that retains it still FAILs. A
short/ungated clip's missing integrated LUFS is the hands' documented
WARN case, not a defect; whole-silence delivery is FAIL. Captions, when
produced, come only from an existing `.words.json` sidecar on a speech
source adjusted to that cue's placement — never a fresh ASR pass on the
mixed master; a source with no sidecar yields no captions for that
interval, and that gap is disclosed rather than filled with an estimate.
A determinism claim is scoped to the same spec + frozen sources + helper
version + environment producing byte-identical PCM, never to a different
free-text description "sounding the same". A matching approval hash
confirms the proposal text was not altered, never who approved it.

For video work carrying an Audio Mix (`audio_workflow: mix`), the tour or
ad QA delegates the master/receipt/caption checks here rather than
reimplementing them — see
[Tour QA](../video-creator/tour.md).

The verdict and delivery-to-client shape are common — see
[common quality assurance](../../SKILL.md); a mix delivery never goes
through the look-before-you-answer vision steps there, per above.
