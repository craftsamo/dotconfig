# Audio hands (audio-creator)

Speech, SFX, music and mix families. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`audio-creator` owns speech, sfx, music and mix and receives filled forms on
A2A `:9909` (receive-only). Its model/fallback/auxiliary pins mirror
ImageCreator's; tools are terminal/file/tts/skills/memory plus the
audio-creator-only `sfx_gen` and `music_gen` toolsets, with no vision,
image/video generation, outbound A2A or external skill library. The existing
profile secret helper already accepts this profile; a dedicated Keychain layer
is not required. Shared contract: [`overview.md`](./overview.md).

Across every family: never invent a listening verdict. Meters, ASR readback,
seeds and waveform/PCM hashes are evidence, not proof of hearing, pronunciation,
performance or a seamless loop; perceptual acceptance is human-reported.

## Speech family

`audio-creator-pipeline/<verb>/speech/` contains three leaves, not a second
menu system. Speech assets use these leaves; the old voice card is retired and
no hands kanban contract is added. Creator keeps ordinary conversational TTS
for its own replies only, never as a speech-asset bypass.

- `generate-speech`: one approved UTF-8 script, up to 600 characters. `voice`
  is `house` or a qualified registered `<engine>:<voice>` ID. House uses the
  ordinary language fallback chain (including online Edge); local-only requests
  choose a qualified local voice, which never falls back. Style/seed require the
  selected engine's advertised capabilities and are rejected, never silently
  dropped, when unsupported. `free` is a media-fee class, not unlimited takes:
  one take plus one corrective by default, failed calls included; packaging
  retries reuse raw audio and do not spend a new take.
- `edit-speech`: approved-order concatenation, boundary-only silence trim,
  pitch-preserving speed, measured two-pass normalization, format conversion.
  No new synthesis. New bundle only, preserving originals; at most 64 inputs
  and 600 seconds. Existing WAV timing sidecars are checked before reuse:
  valid unchanged sidecars reuse exact decoded-duration offsets, timing changes
  and lossy sibling derivatives get fresh ASR, and a stale matching sidecar
  fails.
- `analyze-speech`: input format, decode, loudness/peak/silence and optional
  script readback, returned as findings without a deliverable file.

The shared `speech-media.py` owns track/edit/analyze and keeps WAV +
`.words.json` + SRT + `.take.json` together (48 kHz mono PCM master; optional
Opus or MP3 derivative) in exclusive bundles with measured normalization. It
uses ffmpeg/ffprobe and the already-cached local faster-whisper `base`, never
installing an engine or downloading weights inside a job. Subtitle times are
estimated from ASR, not forced alignment. Exact normalized text matches are
PASS, near matches WARN, missing/mismatched speech FAIL; coverage cannot excuse
missing foreign words. Never re-roll for an ASR spelling variant. None of this
verifies pronunciation, emotion or voice likeness. Returned tool identity/seed
and decoded PCM hashes are evidence; ASR confidence is retained.

Speech can feed a legacy film as a completed input. Vocal-song generation and
standalone audio visualization are withdrawn, not migrated. To withdraw this
family, restore only task-owned configuration/routes, remove the audio-creator
peer/external-root/allowlist entry together and restart the single gateway;
keep all audio, sessions, models and voice data and never reset other work.

### Character voices and performance direction

AudioCreator — and only AudioCreator — gets `character_voices` and
`character_text_to_speech` from the engine-agnostic `tts/character-voice`
plugin (it belongs to neither engine plugin and resolves a provider from the
TTS registry directly). A named character asset is the opposite contract from
ordinary speech: the caller pins the sound, so nothing routes, nothing
substitutes, and the tool never touches `tts.fallback.chain` — reading it would
smuggle language routing into an explicit contract.

- `character_voices` lists every voice registered on a live engine as a
  qualified `<engine>:<voice-id>`; reference-free entries an engine may
  advertise are filtered out (their timbre changes per run). Pass one ID
  verbatim to `character_text_to_speech`; it is also the value for
  `generate-speech`'s `voice` field.
- A bare voice ID is rejected: the engine is half of the identity — the same
  reference renders audibly differently on the two engines.
- A refusal is an error that names the engine and writes no file, never a
  hand-off: an unregistered voice, a stopped engine, or Irodori declining
  English-dominant text. Never retry a refused character voice on the other
  engine.

Style control (emoji vocalisation, free-text `style`/`caption`, `seed`) belongs
only to this explicit contract. `character-voice` reads the provider's
advertised `style_features` and REFUSES any control the named engine doesn't
list; it never learns an engine name for this gating and never drops a control
silently — that would return a file that is not the requested take. Irodori
lists all three controls; Qwen3 lists none.

- **Emoji become performance.** On an engine listing `emoji`, an emoji is acted
  out where it stands (a stifled laugh, sobbing, humming, a sulk) and never
  read aloud. Each one adds audible duration, so use them sparingly. The
  character path parks emoji clusters behind ASCII placeholders across Hermes'
  shared cleaner (`tools/tts_text_normalize.py`) and restores them, so markdown,
  unit and newline handling still apply. Never weaken that cleaner: everywhere
  else emoji are stripped, because an emoji reaching `qwen3-tts` or `edge` is
  read aloud as its name.
- **`style` directs the whole take**: free-text direction in the script's
  language shapes pace and manner while the reference keeps the voice identity.
- **`seed`**: Irodori draws a fresh seed per request when left alone, so the
  tool always pins one (generating it when the caller does not) and returns it.
  Re-rendering that script with that seed rebuilds the same take,
  post-processing included. Qwen3 exposes no seed because its server fixes one
  per voice, so identical requests already reproduce. A seed rebuilds *that
  take*; making a different line match an approved one is continuity work it
  does not buy. Verify reproduction on decoded SAMPLES, not container bytes —
  the delivered Ogg carries a random bitstream serial.

The fallback chain passes no style arguments and must not start doing so;
ordinary chat speech sends the request it always did (on Irodori, an unpinned
take per call). Language routing of that chain, engine installation and voice
data handling are mechanics: see `README.md`.

Character tools resolve on AudioCreator only because the toolset resolver memo
is keyed on profile scope in the hermes-agent checkout (carried as a local
patch); without it a warm `tts` entry in another profile hides them.
Registration-only tests and direct CLI synthesis cannot detect this
gateway-specific loss; `test_audio_creator_routing.py` exercises the real
resolver across scopes. Creator's character tools stay disabled.

## SFX family

SFX is a separate four-leaf subject under `audio-creator-pipeline/<verb>/sfx/`,
not a music or mix family. Creator reads its forms through the existing hands
root; SFX adds no profile, peer, external skill library, kanban contract, gain
automation, TTS or tour change.

- `create-sfx`: eight deterministic local kernels — click, beep, chime, whoosh,
  riser, pop, ui-tick, noise-burst. The seed controls noise, not a generative
  model; identical recipe/environment parameters reproduce decoded master PCM.
- `generate-sfx`: local `local:stable-audio-3-medium` is installed and is the
  default when `engine` is omitted; `fal:elevenlabs-sfx-v2` must be named
  explicitly. Neither engine ever falls back to the other, automatically or
  silently.
  - Local takes a `seed` (default 0, range 0..2^32-1, returned with the
    result); attempt N uses `(base seed + N - 1) mod 2^32`. It rejects
    `loop=true` and any `prompt_influence`/`paid_approved`/`max_usd` outright
    rather than silently dropping them, and reports actual spend as `$0`.
  - fal needs the client's explicit current-work paid approval of prompt,
    seconds, loop, call cap and `max_usd` before any spend. It supports `loop`
    and `prompt_influence`, has NO seed, and requests cap at 21.5 s (0.5 s
    padding/drift headroom under the helper's 22 s limit).
  - `max_calls` defaults to 4 (3 variants + 1 corrective) on local; fal requires
    an explicitly approved cap. Hard cap 8; every attempt, including failures,
    counts. The default is a proposal on either engine, never a spend grant.
    Metadata cost stays `metered` because the leaf can still spend on fal.
- `edit-sfx`: trim, duration-changing pitch, reverse, pad both ends, fades,
  explicit true-peak gain and format conversion, always into a new bundle.
  Never generates.
- `analyze-sfx`: native-format measurements and findings without a delivery.
  Never generates.

`sfx-media.py` uses numpy and ffmpeg/ffprobe, with no ASR or model downloads.
It freezes a single regular local source (<=16 MiB, <=22 seconds), preserves
mono/stereo including anti-phase channels, and publishes new 48 kHz s16le PCM
WAV bundles plus `.take.json` atomically, never replacing an existing directory.
Native input evidence is recorded separately from the resampled master and
lossy derivatives. PCM hashes are f32le decoded samples at the reported
rate/channel count, not speech's mono s16le convention. Silence/clipping fails;
short SFX with no integrated LUFS is a WARN, not a reason to re-roll. Peak,
clipping, attack and boundary samples are measurements, never proof of hearing
or of a seamless loop. Speech's helper and its timing-sidecar contract are
unchanged.

The standalone `plugins/audio_gen/sfx-gen` plugin registers only for
audio-creator, using the dedicated `sfx_gen` CLI/A2A toolsets. `sfx_engines` is
a free capability lookup; `sfx_generate` starts, resumes or advances a bounded
job. Frozen job state fixes the engine/controls/budget and counts an attempt
before a paid submission; request IDs survive disconnections. `resume` never
regenerates. An ambiguous fal submission stops for manual reconciliation, while
a confirmed completed request's 400/422 rejection consumes an attempt and
permits the next approved corrective. Paid submission is one non-retrying HTTP
POST (never the SDK's automatic submit retries); only request-ID retrieval uses
the SDK's retry path. `FAL_KEY` resolves from profile scope into an explicit SDK
client, never a process-env fallback. The tool's acknowledgment of paid approval
is an operating contract, not proof of caller identity.

Leaf commands use a literal Python path (or unquoted `~/ghq/...`), never
`$(ghq root)` in the executable — the terminal guard refuses a nested executable
body. Resolve a different ghq root separately, then run the absolute path. A
packaging repair reuses the surviving raw WAV/receipt and consumes no generation.

Finished SFX reach video only as `create-ad` WAV cues ([`video.md`](./video.md)
"Ad family") or as Mix sources.

### Local Stable Audio 3 Medium runtime

`hermes/scripts/stable_audio3.py` adopts a pinned checkout + weights + a
hash-locked Python 3.11 MLX venv under the gitignored
`hermes/local/stable-audio-3/`; code and weight pins live in
`engines/stable-audio-3/pins.json`, dependencies in `requirements.lock`.
Installation is a maintainer-only one-time step
(`stable_audio3.py install --accept-terms`); jobs never install, download or
mutate the runtime. `check` / `check --full` report readiness: the fast check
trusts stat fingerprints (a version-pin guarantee, not a tamper-proof sandbox),
`--full` re-hashes weights and re-collects the dependency manifest.

**Headroom before quantization (2026-09-23).** Upstream `sa3_mlx.save_wav`
hard-clips the float decoder output to [-1, 1] before writing 16-bit PCM, and
Medium routinely decodes past full scale: all three approved music takes of the
Creator A/B arrived clipped (+0.1 to +1.3 dBTP), sfx-/music-media refused them,
and edit-music cannot repair a clipped source, so the video shipped without
music. The adapter now runs the unmodified upstream script through a small
`python -c` bootstrap that wraps `save_wav` with one constant gain whenever the
sample peak exceeds `HEADROOM_CEILING_DBFS` (-1.0) — no limiter, no loudness
normalization, quieter takes untouched — and records `headroom`
(`pre_gain_peak_dbfs`, `gain_db`) in `take.json`. Re-rendering the failed
seed-0 prompt: pre-gain +0.27 dBFS, −1.27 dB applied, true peak −0.56 dBTP,
`music-media.py track` PASS. The headroom lives in the adapter, so it changed the
install fingerprint; activate an adapter edit with `stable_audio3.py refresh
--previous-adapter <old source>`, never a reinstall.

Each render is a brand-new subprocess — no LaunchAgent, no port, no
GPU-resident process — that inherits the shared runtime lock (one
install-or-render at a time; the child keeps the lock across a parent death)
and is killed by process-group SIGKILL at a 180 s timeout. `HF_HUB_OFFLINE` /
`TRANSFORMERS_OFFLINE` prevent lazy downloads during render; they are not a
network-sandbox claim. SFX `render()` stays <=21.5 s; music uses its own
`render_music()` entry and bounds on the same install and lock — never a second
engine, install or daemon.

Job state (schema v2) freezes payload/runtime identity at `start`. `resume`
only re-validates the saved `take-NN/raw.wav` + `take.json` + `inference.log`
receipt (engine, model commit/revision, runtime fingerprint, exact request, the
raw WAV's hashes) against the frozen attempt. A running attempt with no bundle
reports `pending` while the lock is busy; once the lock is free with still no
bundle, it is marked `failed` and stays counted, and `next` may spend the
remaining grant. Raw audio is 44.1 kHz 16-bit stereo; `sfx-media.py track`
repackages it into the 48 kHz bundle given the take's real `take.json` via
`--take-file` (never a fal `.tool.json`).

Drift: runtime adapter edits invalidate the install fingerprint; the maintainer
runs `stable_audio3.py refresh --previous-adapter PATH`, which verifies the
previous adapter fingerprint and the whole existing install offline before
updating the marker (details: `README.md`). Never bypass drift checks or rewrite
existing job receipts; a completed resume stays valid and `next` detects drift.
The stat fingerprint is inode + mtime_ns + size — never `st_dev`, which macOS
renumbers across reboots and would report false drift that pushes jobs toward
paid fal. `_stat_matches` compares only those three keys, so an older marker
still carrying `dev` stays valid without a rewrite. If `check` reports stat
drift after a reboot, suspect a new volatile field before the weights —
`check --full` hashing clean while the fast check fails is the tell. `status()`
full mode hashes weights instead of stat-checking them, so a full pass does not
prove the fast guard is green.

Licensing: the upstream code is MIT; the Medium weights download anonymously at
the pinned revision and carry Stability AI's Community License plus Gemma terms.
This install is a personal-evaluation acceptance — no commercial registration
and no implied blanket commercial authorization (cite the primary license pages
when that matters). The old `local:stable-audio` (Stable Audio Open, 401-gated)
is retired; never describe Medium as gated, blocked or "coming soon".

## Music family

Music is instrumental BGM or a short melodic opener/closer under
`audio-creator-pipeline/<verb>/music/` — not Song and not Mix. A full song with
lyrics/singing or standalone sound design is `no skill fits`, never
approximated by a music leaf; combining finished sources is "Mix family" below.
Create/generate cap at 60 s; edit/analyze accept up to 600 s / 128 MiB. Music
implies no new profile, peer, external skill library, kanban contract, tour/MV
finish, song, secret, model download or launch service.

- `create-music`: an exact deterministic score of five closed synthetic
  waveforms (sine/triangle/pulse/fm-bell/noise), authored by AudioCreator from
  the client's direction and rendered locally at zero spend, zero network.
  `minimal-electronic`/`chiptune`/`ambient-synth` are starting styles, not a
  closed menu; custom direction must fit the five-waveform palette. A described
  real-world/sampled instrument routes to `generate-music`.
- `generate-music`: a compact text prompt to `local:stable-audio-3-medium` by
  default (`engine` omitted, $0, seed-controlled) or an explicitly chosen
  `fal:stable-audio-3-medium` (metered, also seeded; needs current-work
  approval and a dollar cap). Neither direction falls back; `music_engines` is a
  free capability lookup.
- `edit-music`: processes one source — trim, repeat-to-length with a
  crossfaded loop seam, fade in/out, gain or two-pass LUFS normalization with a
  -1 dBTP ceiling — always into a new bundle; never resynthesis.
- `analyze-music`: local numpy tempo/beat/key/triad/structural-boundary
  estimates plus format/loudness/clipping findings, no delivery; half/double
  BPM and key ambiguity are disclosed. It also serves standalone musical
  analysis of any client-supplied song, including vocal music, but never lyric,
  singing, genre, mood or instrument verdicts.

Users need not author a score or prompt. Both creation leaves are TWO rounds,
unconditionally, in one resident work conversation. Round A (no
`approved_plan`/`approval_sha256`) has no audio, no uploads and no automatic
reference-audio conditioning: it writes `form.json` + `arrangement.md` + the
exact artifact (`score.json` for create, `prompt-v<N>.txt` for generate), and
`scripts/music_plan.py propose` freezes the effective form, exact score/prompt
and reference hashes into `proposal-v<N>/proposal.md`, returning it and its
SHA-256 with zero spend. Its frozen `score.json` or `generation-prompt.txt` is
the artifact to use, including when packaging an older take after a correction.
Only a second handoff with that EXACT `approved_plan` + `approval_sha256`,
relayed by Creator in the same work conversation, releases a `music-media.py
create` render or a `music_generate` call; hash matching is integrity, never
approver authentication. A changed creative field needs a new proposal and
approval. Attempts never reset on resume or corrective reapproval; a corrected
approved prompt keeps the consumed-call ledger and the frozen
engine/duration/seed/budget.

The standalone `plugins/audio_gen/music-gen` plugin registers only for
audio-creator (`music_gen` CLI/A2A toolset: `music_engines`, `music_generate`
with `action: start | next | resume`). Its approval/state/evidence machinery
mirrors `sfx-gen`: hash-bound approved manifest, frozen job settings, an attempt
ledger counting every call including failures, single non-retrying paid POSTs,
and a `resume` that only re-validates a checkpointed receipt. Local default
grant is **2 variants + 1 corrective (max 3), hard cap 8**; fal requires an
explicitly approved `max_calls` and a `max_usd` covering it, never an implicit
budget. Metadata cost stays `metered`; actual local spend reports `$0`.

`music-media.py` owns `create`, `track`, `edit` and `analyze`, with 48 kHz PCM
bundles and bounded local tempo/key/activity estimates; instruments, genre and
vocal absence stay unverified. Its PCM hash convention and freeze/bundle rules
are documented in the leaves' `SKILL.md`. Finished music reaches video through
`create-ad`'s existing WAV cues or Mix.

Front matter: music leaves are the tightest fit for the 4,000-character
discovery prefix ([`overview.md`](./overview.md) "The form"); test the actual
`_find_all_skills` names, not just the topology validator. Runtime write
protection checks literal operations/targets, not `mv` inside a job path; keep
the music proposal CLI's guard-plus-proposal regression for that case.

Vocal-song generation and standalone audio visualization remain withdrawn
without a hands replacement; a request for either is `no skill fits`, never
routed to a core/external stand-in.

## Mix family

Mix places already-finished sources on one shared timeline under
`audio-creator-pipeline/<verb>/mix/`. It is not synthesis and not a music/SFX
family: no generation, loops, speed/pitch changes, EQ, reverb, source
separation or video assembly — a request needing those routes to the fitting
leaf (generate-speech/create-sfx/generate-sfx/create-music/generate-music)
first, and a music/SFX leaf is still not itself a mixer. Mix adds no engine,
plugin, toolset, secret, peer, daemon, profile or kanban contract and shares no
runtime with SFX/Music's Stable Audio install.

- `create-mix`: 1-16 standalone local speech/sfx/music sources
  (WAV/FLAC/Ogg/MP3/AIFF, each <=128 MiB, <=512 MiB combined, <=600 s decoded),
  placed as <=32 cues on a 1-600 s timeline with gain/fade/piecewise-dB-envelope
  automation, rendered to one 48 kHz PCM master. Without an exact `arrangement`,
  AudioCreator authors relative cue placement from `direction`/`must_keep`/`note`
  — no user-written spec required. A supplied `arrangement` is preserved
  verbatim, never reinterpreted; an out-of-range/nonexistent-source control is
  a `Q<n>:`, never silently clamped. An optional `timing` file fixes named cues'
  exact `start`/`source_start`/`duration`, never adjusted behind approval.
- `edit-mix`: revises one existing bundle from a plain-language `changes`
  request against its frozen `mix.json` and `sources/` — never re-uploaded or
  re-synthesized audio, never stem separation from the master. An audio-inert
  request (e.g. renaming only) is refused as a no-op revision.
- `analyze-mix`: format/duration/channels/peak/true-peak/clipping/integrated-LUFS
  findings on any finished mix file, plus the recorded cue/source placement when
  a previous bundle directory is supplied (its source must hash-match that
  bundle's master). Findings only — no delivery file, no fresh ASR pass.

`mix-media.py` owns `propose`, `render`, `analyze` and `verify` (re-validates a
bundle for reuse without rerendering). `create-mix`/`edit-mix` are TWO rounds,
unconditionally: round A writes `spec.json` + `description.md` and runs
`propose` (`--previous <bundle>` for edit), returning only a zero-render
`proposal-v<N>/proposal.md` + SHA-256; only a matching Creator-relayed
`approved_plan` + `approval_sha256` in the same work conversation releases the
render. Any changed source, cue placement, gain/fade/envelope, duration,
`target_lufs` or `true_peak_dbtp` needs a new proposal. `target_lufs` has no
hidden default — an explicit authored choice, `null` included;
`true_peak_dbtp` defaults to -1 unless direction calls for otherwise.

Every source stays the original standalone file, frozen and hash-verified
against its `sources/` copy before use. A source's own existing defect (e.g.
prior clipping) is kept and reported, never silently corrected, and a mix that
keeps it still FAILs, as does whole-silence delivery. Normalization is measured
constant gain only, never loudnorm's implicit dynamic-limiter fallback;
infeasible loudness/peak targets FAIL; float-bus overrange before an approved
scalar reduction is warned, not confused with already-clipped source PCM;
stereo-to-mono cancellation is warned and recorded. Captions (`captions.json` +
`mix_<slug>.srt`) come only from an existing `.words.json` sidecar on a speech
source, timing-adjusted to the cue's placement — never a fresh ASR pass on the
mixed master; overlapping spoken cues or a trim crossing a word/caption boundary
is refused. Determinism is scoped to same spec + frozen sources + helper version
+ environment → byte-identical PCM. The family is `cost: free` throughout —
deterministic placement/gain/fade/sum on decoded PCM, with no attempt ledger or
paid-approval gate beyond the approval hash. Exact schema: the leaf's
`references/arrangement.md`.

**Video integration.** A finished sfx/speech/music WAV may feed `create-mix` as
a source, the same way a finished WAV may feed `create-ad` as a cue — separate
forms, never folded into one handoff, and never a direct hands-to-hands call.
Ad/Tour opt in with `audio_workflow: mix`: Creator brokers a preliminary timing
proposal from the video leaf, then the Mix proposal/approval/render, then the
ordinary video plan/preview approval using the real master/receipt hashes. An
approved plan contains no dummy audio or placeholders. `mix_audio.py` validates
the staged subset. Only the master plays; kept footage audio is a conflict.
Tour binds `mix-caption-N` text/timing to the distinct Mix `captions.json`;
never relax speech's `words.json` hash check or rewrite its hash. Final decoded
audio duration and peak are measured again. Omitted Mix fields preserve frozen
v1/v2/v3 behavior; MV/clip finishing is unchanged. The synthetic fixture
(`scripts/tests/fixtures/mix-video/example.py`) verifies wiring, not real
speech/ASR quality or a live Creator conversation. Existing resident
conversations may retain older instructions; validate with fresh sessions.
