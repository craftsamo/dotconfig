# Plan — audio-creator: mix

Read [common plan](../../SKILL.md) first.

`create-mix` places 1-16 already-finished, standalone local speech/sfx/
music files (WAV/FLAC/Ogg/MP3/AIFF, each ≤128 MiB, ≤512 MiB combined,
≤600 s decoded) onto one shared timeline (≤32 cues, ≤600 s total) with
gain/fade/piecewise-dB-envelope automation and renders one 48 kHz PCM
master. It never synthesizes or generates a component sound (that stays
with generate-speech/create-sfx/generate-sfx/create-music/generate-music
first), never loops a source to length, and never applies EQ, reverb,
source separation, or assembles video — a request needing any of those
is `no skill fits` for this leaf, routed to the fitting leaf first, never
approximated here. Fill `what_for`/`sources`/`direction`/`duration` with
the client; `arrangement` (exact per-cue start/gain/fades/envelope) is
optional and, when supplied, preserved verbatim — never reinterpreted,
and an out-of-range or nonexistent-source control is a `Q<n>:`, not a
silent clamp. AudioCreator authors relative cue placement from
`direction`/`must_keep` when no `arrangement` is given; no user-written
spec is required. An optional `timing` file constrains named cues'
exact `start`/`source_start`/`duration` and is never adjusted behind
approval.

Like [music](music.md), this is TWO rounds, always: the first handoff
carries no `approved_plan`/`approval_sha256` and returns only a
`proposal-v<N>/proposal.md` and its SHA-256 with zero renders — show it
to the client the same way as a music proposal. Only a second handoff
with that exact `approved_plan`+`approval_sha256`, in the same
conversation, releases the render. A changed creative field (any source,
cue placement, gain/fade/envelope, duration, `target_lufs`,
`true_peak_dbtp`) needs a new proposal, never a render against stale
approval text. `target_lufs` has no hidden default — AudioCreator states
it as an explicit authored choice (`null` is valid) rather than leaving
it implicit. This leaf assembles already-finished sources; it spends no
provider fee and takes no attempt grant (`cost: free` throughout) — see
[common plan](../../SKILL.md) "Budget lines" for the metered leaves this
one differs from.

`edit-mix` revises one existing mix bundle (added/removed/moved cues,
re-gained/re-faded automation, a changed duration or loudness target)
from a plain-language `changes` request against the previous bundle's
frozen sources and spec — it never re-uploads or re-synthesizes a
source, and never separates stems out of the previous master. It is the
same two-round shape as `create-mix`. `analyze-mix` returns
format/loudness/clipping/true-peak findings on any finished mix file,
and, when a previous bundle directory is supplied, the actual recorded
cue/source placement from its `mix.json` — findings only, no delivery
file. A finished sfx/speech/music WAV may feed `create-mix` as one of
its `sources`, the same way it may feed `create-ad` as a distinct
placed cue; the two are separate forms, never folded into one handoff.
