# Ambient synth

Achievable palette: `sine`/`triangle` sustained pads (long note
`duration` values, low-to-moderate `velocity`), `fm-bell` for sparse,
widely-spaced accent notes, low-gain `noise` as an air/texture bed. Favor
few simultaneous tracks (1-3), long sustained notes and wide spacing
between events - this style is defined by sparseness and sustain, not by
any reverb/delay effect this schema cannot apply (there is no reverb send
or delay control here; sustain must be written as long note `duration`
values instead).

Controls NOT available: no reverb/delay send, no filter automation, no
stereo width control per track beyond the fixed `pan` value.

Example adaptation: an ambient-synth background bed might use one `sine`
pad holding whole-piece-length notes and one `fm-bell` accent every few
bars, `gain_db` kept low on both.

QA cue: check that note `duration` values are actually long/sustained
(not short, staccato notes) and that track count stays low; a dense,
short-note score mislabeled ambient-synth is a mismatch to flag before
approval.
