# Commission — audio-creator: music

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a deterministic instrumental cue composed of five closed electronic waveforms (sine/triangle/pulse/fm-bell/noise), from an authored score | `create-music` | free, zero network calls; instrumental BGM/melodic opener-closer only, at most 60s; two-round proposal-then-approval gate |
| a described instrumental cue/BGM in real-world/sampled instrumentation, default engine | `generate-music` (local Stable Audio 3 Medium, engine omitted) | free ($0), no paid approval needed; takes a seed (default 0); two-round proposal-then-approval gate; default attempt cap 2 variants + 1 corrective, hard cap 8 |
| the same, via the explicitly chosen paid engine | `generate-music` (`engine: fal:stable-audio-3-medium`) | metered; explicit current-work paid approval of engine/prompt/duration/seed/attempt cap/USD estimate before any spend; no local fallback |
| trim / loop-crossfade / fade / gain / two-pass LUFS normalization of an existing music file | `edit-music` | free; preserves the original, never resynthesizes |
| tempo/beat/key/structural-boundary findings on an existing music file, standalone or from this pipeline | `analyze-music` | free; measured/estimated findings only with half/double BPM and key ambiguity disclosed, never a listening, genre, mood, instrument, lyrics or vocal-performance verdict; deliver may be omitted |

## Choosing and filling

### Budget

Local default allowance is 2 variants + 1 corrective (hard cap 8), the
same attempt-counts-failures rule as [sfx](sfx.md); fal needs its own
explicit cap and USD estimate, never a default budget. `create-music` and
deterministic `analyze-music`/`edit-music` spend no provider fee. For
another subject, read that subject's reference and hands leaf for its
allowance.

### An authored score or a described cue, not a song

Music is scoped to instrumental BGM or a short melodic opener/closer,
create/generate at most 60 seconds (edit/analyze accept up to 600 seconds
and 128 MiB); a full song with lyrics/singing or standalone sound
design/SFX is `no skill fits` — never approximated by either music leaf.
Combining already-finished speech/sfx/music sources onto one timeline is
`create-mix`/`edit-mix` in
[mix](mix.md), never a
music leaf approximating a mixer. Fill
`what_for`/theme/style/duration and any optional
`direction`/`tempo`/`ending`/`must_keep`/`reference_audio` with the
user the same way as any other leaf: `theme_detail`/`must_keep`
override conflicting theme defaults, and `reference_audio` is never
uploaded — a user who wants an objective tempo/key/structure
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
`proposal-v<N>/proposal.md` and its SHA-256 with zero spend — show the user
the file with your summary and an approval question. Only a second handoff with that EXACT
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
user-supplied song handed over for arrangement/harmony-style
analysis — not only this pipeline's own deliveries.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's `create-music`/`generate-music`, both rounds | `kind="work"` from the proposal onward; keep the proposal, relayed approval and production in the same resident conversation even though round A makes no audio call and local generation spends $0. `edit-music`/`analyze-music` use inquiry only when known to finish in one reply; otherwise work |

## Round-trip and approvals

For `create-music`/`generate-music`, relay round A's handoff with no
`approved_plan`/`approval_sha256` and expect back only a
`proposal-v<N>/proposal.md` path and its SHA-256, zero spend. Show the user that exact
proposal and hash for approval; only a matching second
handoff (`intent: revise <previous delivery>`, the same
`approved_plan`+`approval_sha256`) releases a render or `music_generate`
call. A changed creative field needs a new proposal, never a generation
against stale approval text. For `generate-music`, if no engine is
named audio-creator uses the local Medium default (no paid approval to
relay); an explicit `fal:stable-audio-3-medium` request needs the
approved engine/prompt/duration/seed/attempt-cap/USD estimate relayed
exactly as approved, never audio-creator's own `music_engines`
availability finding standing in for that approval. `edit-music`/
`analyze-music` are free, bounded one-reply leaves like `edit-sfx`/
`analyze-sfx` (see [sfx](sfx.md)); `analyze-music`'s `deliver` may
likewise be omitted.
