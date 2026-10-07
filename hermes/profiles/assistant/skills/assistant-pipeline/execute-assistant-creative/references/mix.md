# Commission — audio-creator: mix

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| already-finished speech/sfx/music sources placed on a shared timeline with authored gain/fade/envelope automation, from a one-sentence purpose and plain-language direction | `create-mix` | free; two-round proposal-then-approval gate, zero-render `proposal-v<N>/proposal.md` first, renders locally only after the user's relayed approval; no new synthesis, looping, EQ, reverb or source separation |
| revision of an existing frozen mix bundle from a plain-language change request | `edit-mix` | free; loads the frozen sources and previous spec, authors a full revised plan; same two-round proposal-then-approval gate; a FAILed bundle cannot be revised; original sources are preserved, never re-synthesized |
| measured findings on an existing mix — format/loudness/clipping/true-peak, and with its own bundle the recorded source/cue placement from mix.json | `analyze-mix` | free; findings only, no deliverable file, deliver may be omitted; not a listening/perceptual verdict, not repair, not a fresh ASR pass over the mixed master |

## Choosing and filling

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
the user; `arrangement` (exact per-cue start/gain/fades/envelope) is
optional and, when supplied, preserved verbatim — never reinterpreted,
and an out-of-range or nonexistent-source control is a question to the
user, not a silent clamp. AudioCreator authors relative cue placement from
`direction`/`must_keep` when no `arrangement` is given; no user-written
spec is required. An optional `timing` file constrains named cues'
exact `start`/`source_start`/`duration` and is never adjusted behind
approval.

Like [music](music.md), this is TWO rounds, always: the first handoff
carries no `approved_plan`/`approval_sha256` and returns only a
`proposal-v<N>/proposal.md` and its SHA-256 with zero renders — show it
to the user the same way as a music proposal. Only a second handoff
with that exact `approved_plan`+`approval_sha256`, in the same
conversation, releases the render. A changed creative field (any source,
cue placement, gain/fade/envelope, duration, `target_lufs`,
`true_peak_dbtp`) needs a new proposal, never a render against stale
approval text. `target_lufs` has no hidden default — AudioCreator states
it as an explicit authored choice (`null` is valid) rather than leaving
it implicit. This leaf assembles already-finished sources; it spends no
provider fee and takes no attempt grant (`cost: free` throughout) — see
[commissioning](../SKILL.md) "Filling the form" for the metered leaves
this one differs from.

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

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's `create-mix`/`edit-mix`, both rounds | `kind="work"` from the proposal onward, the same two-round shape as `create-music`/`generate-music` (see [music](music.md)); keep the proposal, relayed approval and render in the same resident conversation. `analyze-mix` is a free, bounded one-reply leaf and uses the generic `inquiry` row in [commissioning](../SKILL.md) |

## Round-trip and approvals

For `create-mix`/`edit-mix`, relay round A's handoff with no
`approved_plan`/`approval_sha256` and expect back only a
`proposal-v<N>/proposal.md` path and its SHA-256, zero renders. Show the user
that exact proposal and hash for approval; only a
matching second handoff (`intent: revise <previous delivery>`, the same
`approved_plan`+`approval_sha256`) releases the render. A changed
source, cue placement, gain/fade/envelope, duration or loudness target
needs a new proposal, never a render against stale approval text.
For video work, request `audio_workflow: mix` from create-ad/create-tour
before its formal plan — see
[ad](ad.md) and
[tour](tour.md)
for the video-side halves of that handoff. Relay the resulting frozen
timing path/hash to AudioCreator; AudioCreator authors gains/ducking, not
the video's required cue times. After Mix approval/render, return
`mix_bundle` to VideoCreator so its normal approvals bind the REAL audio
bytes. No placeholders or pending assets in an approved video plan; no
source-stem double playback.
`analyze-mix` is a free, bounded one-reply leaf like `analyze-sfx`/
`analyze-music` (see [sfx](sfx.md) / [music](music.md)); its `deliver`
may likewise be omitted, and it works on any finished mix file, not only
this pipeline's own deliveries.
