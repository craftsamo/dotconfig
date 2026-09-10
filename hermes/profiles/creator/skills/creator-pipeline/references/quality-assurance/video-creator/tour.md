# Quality assurance — video-creator: tour

Read [common quality assurance](../index.md) first.

Review the hands' report and supplied preview frames against the client's
approved semantic flow, fidelity and literal intro/outro/style directions.
The hands own source-time, decode and audio measurements; Creator reads
their evidence, preserves its limitations and decides whether it meets
the client's intent. Do not run those checks again.

## Frozen preview, not continuous-motion certification

`preview: yes` (the default) stops the job at a frozen source project and
snapshots for actual client approval; a resume renders that unchanged
approved project into a fresh final directory — never a self-approved or
silently re-authored one. Compare the supplied boundary/action/result
frames with the approved flow: a modal appearing, a selection updating,
typed text accumulating. Moving a screenshot alone does not establish
those changes. Read the hands' full-decode, dimensions, fps and duration
results without rerunning them. Review samples are not complete temporal
or listening evidence; carry unsampled motion as unverified.

## Source-time mapping and keep/mute

For supplied or captured footage, read the hands' source-time mapping
and keep/mute evidence against the approved source ranges and sound
choice. Do not seek through the originals to recompute that mapping or
relisten to the audio. Missing evidence remains a gap to report, not a
passed check or a reason to silently discard the requested sound.

## Mix provenance

With `audio_workflow: mix`, read the reported master/receipt/caption and
timing validation status; the Mix master must be the tour's only audio,
not a second playback alongside its source stems or kept footage audio.
Preserve a FAIL receipt and the hands' measured final duration/true-peak
result against the approved plan. Do not recompute hashes, decode audio
or interpret matching measurements as listening or playback-sync proof.
See [Tour build](../../build/video-creator/tour.md) for the Mix handoff.

## Privacy

Privacy masking/redaction is not implemented for capture. A scope with
private regions or credentials is refused, not silently accepted with a
promised overlay.

No new measurement is taken here. Use the common visual review and
verdict/delivery procedure, with the hands' failed or unverified checks
left explicit.
