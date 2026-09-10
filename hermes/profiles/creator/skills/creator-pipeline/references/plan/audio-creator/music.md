# Plan — audio-creator: music

Read [common plan](../index.md) first.

## Budget

Local default allowance is 2 variants + 1 corrective (hard cap 8), the
same attempt-counts-failures rule as [sfx](sfx.md); fal needs its own
explicit cap and USD estimate, never a default budget. `create-music` and
deterministic `analyze-music`/`edit-music` spend no provider fee. For
another subject, read that subject's Plan reference and hands leaf for its
allowance.

## An authored score or a described cue, not a song

Music is scoped to instrumental BGM or a short melodic opener/closer,
create/generate at most 60 seconds (edit/analyze accept up to 600 seconds
and 128 MiB); a full song with lyrics/singing or standalone sound
design/SFX is `no skill fits` — never approximated by either music leaf.
Combining already-finished speech/sfx/music sources onto one timeline is
`create-mix`/`edit-mix` in
[Placing finished sources, not composing a new one](mix.md), never a
music leaf approximating a mixer. Fill
`what_for`/theme/style/duration and any optional
`direction`/`tempo`/`ending`/`must_keep`/`reference_audio` with the
client the same way as any other leaf: `theme_detail`/`must_keep`
override conflicting theme defaults, and `reference_audio` is never
uploaded — a client who wants an objective tempo/key/structure
measurement from a reference file needs a separate `analyze-music` call
first, its findings fed back into this form.

An exact deterministic composition from the five closed score waveforms
(sine/triangle/pulse/fm-bell/noise) is `create-music`: free, zero
network calls. `minimal-electronic`/`chiptune`/`ambient-synth` are starting
styles; custom directions within the five-waveform palette remain valid.
A described real-world/sampled-instrument direction outside that palette is `generate-music`
instead; it defaults to the local Stable Audio 3 Medium engine (`engine`
omitted, $0 spend, seed-controlled, default `style` options `ambient`/
`electronic`/`lofi`/`acoustic`/`jazz`/`orchestral`), with an explicitly
named `fal:stable-audio-3-medium` request as the one metered path,
gated on explicit current-work paid approval of engine/prompt/duration/
seed/attempt cap/USD estimate exactly like generate-sfx's fal
alternative — and it, too, takes no automatic fallback in either
direction.

Both leaves are TWO rounds, always: the first handoff carries no
`approved_plan`/`approval_sha256` and returns only a
`proposal-v<N>/proposal.md` and its SHA-256 with zero spend — show it to the
client (a human: the file plus your summary and one `clarify`
question for approval; the assistant: the path, hash, and a text
approval question). Only a second handoff with that EXACT
`approved_plan`+`approval_sha256`, in the same conversation, releases a
render or a `music_generate` call. A changed creative field needs a new
proposal and a new approval, never a generation against stale approval
text.

`edit-music` changes an existing file (trim/loop-crossfade/fade/gain/
two-pass LUFS normalize) and never resynthesizes — a defect in the actual
composed music routes back to a `create-music`/`generate-music`
proposal, not a hand-patched edit. `analyze-music` returns tempo/beat/
key/structural-boundary findings only, with half/double BPM and key
ambiguity disclosed, never a genre/mood/instrument or
lyrics/vocal-performance verdict, and works standalone on any
client-supplied song handed over for arrangement/harmony-style
analysis — not only this pipeline's own deliveries.
