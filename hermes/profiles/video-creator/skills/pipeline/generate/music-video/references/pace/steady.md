
# Pace: Steady

Intent: pace sets the accent of action and camera, how long a pose or shot
holds, and - only when the clip is multi-shot - the edit rhythm between
those shots. It does not choose transition type, imply a target BPM, or
authorize post-render speedup; those are separate decisions. Steady means an
even, readable cadence across the clip: varied phrase lengths that still
balance out, not identical 3-4 second held beats repeated like a metronome.
Movement and holds should feel consistent in energy without being
mechanically uniform in duration.

Prompt guidance: "<subject> carries <action> at an even, readable pace -
each phrase of movement given a slightly different length while the overall
energy stays consistent, avoiding a metronomic repeat of the same beat
length." Rewrite the action and phrasing around the actual brief; keep the
sentence shape, not the exact words.

Avoid: do not describe every beat as the same fixed duration (e.g. every
hold at "3-4 seconds") - that produces a mechanical loop feel, not a steady
rhythm. Do not silently drift toward relaxed's long holds or snappy's sharp
accents; if the client's description asks for a specific mismatch, follow it and
ask/propose when it conflicts with other cues instead of forcing the
nearest enum.

QA cues: sampled/timecoded frames are the available evidence for whether
phrase lengths vary while energy stays balanced - they cannot confirm
uniform rhythm across the full unsampled duration. Flag any run of visually
identical held beats as a mismatch with steady pacing.
