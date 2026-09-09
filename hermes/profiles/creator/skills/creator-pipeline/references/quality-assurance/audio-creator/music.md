# Quality assurance — audio-creator: music

Read [common quality assurance](../index.md) first.

A music delivery is reviewed the same way as [speech](speech.md) and
[SFX](sfx.md): never opened with vision, never relistened to. For a
proposal round, read the theme/style/direction/ending expanded into the
actual score or prompt language against what the client asked, and
confirm the approval hash matches the exact text before any spend was
released. For a rendered take, read the hands' full-decode/duration/format measurements — and,
for `analyze-music`, its tempo/beat/key/triad/structural-boundary estimates —
against the client's intent. Tempo comes back with its half/double BPM
ambiguity disclosed and key with its own ambiguity; carry both forward
exactly as reported rather than picking the one number that sounds
right. Triad candidates are per two-second window; low-energy or ambiguous
windows may be unavailable, and similarity is not a probability.
Structural-boundary candidates are timestamped estimates of
measurable change, never semantic verse/chorus/section labels. What
this QA is NOT: a genre, mood or instrument-identity guess, a vocals-
absence confirmation, or a listening verdict on whether the piece
"works" — an "instrumental" direction in a generate-music prompt is a
requirement that was asked for, not evidence it was honored, so state
that gap explicitly rather than resolving it yourself. A `create-music`
delivery's determinism claim is scoped to the same score + renderer +
environment producing byte-identical PCM, never to a different
free-text description "sounding the same".

The verdict and delivery-to-client shape are common — see
[common quality assurance](../index.md); a music delivery never goes
through the look-before-you-answer vision steps there, per above.
