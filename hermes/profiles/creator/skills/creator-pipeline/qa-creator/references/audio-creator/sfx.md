# Quality assurance — audio-creator: sfx

Read [common quality assurance](../../SKILL.md) first.

An SFX delivery is reviewed the same way as [speech](speech.md): never
opened with vision, never relistened to. Read the hands' full-decode/peak/true-peak/
LUFS/clipping measurements against what the client asked for (a
matching kind for create-sfx, a matching prompt/seconds/engine for
generate-sfx). A waveform or a LUFS number is evidence, not a listen —
do not tell the client the sound was heard. A short/transient clip's
missing `integrated_lufs` is the hands' documented WARN case, not a
defect: never send it back for a re-roll on that basis alone. Preserve
every WARN and FAIL exactly as reported, including a lossy derivative's
independently measured peak and any dependency error distinguished from
a measured FAIL. On a local Medium delivery, a repeated `seed` matching
the hands' reported decoded-PCM hash is reproducibility evidence, not a
listened confirmation. `boundary_sample_deltas` on a fal `loop: yes`
request is descriptive only, never proof of a seamless loop; carry that
gap forward rather than resolving it yourself.

The verdict and delivery-to-client shape are common — see
[common quality assurance](../../SKILL.md); an SFX delivery never goes
through the look-before-you-answer vision steps there, per above.
