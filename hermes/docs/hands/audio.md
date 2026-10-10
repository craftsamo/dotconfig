# Audio hands (audio-creator)

Speech, SFX, music and mix families of the audio hands. Read it when changing or commissioning an audio leaf. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

`audio-creator` owns speech, sfx, music and mix and receives filled forms on
A2A `:9909` (receive-only). Its tools are terminal/file/tts/skills/memory plus
the audio-creator-only `sfx_gen` and `music_gen` toolsets: no vision,
image/video generation, outbound A2A or external skill library. Shared
contract: [`overview.md`](./overview.md). Every proposal/approval below follows
the one rule in [`broker.md`](../broker.md) "Approvals, budget and consent":
relayed by the Assistant in the same work conversation, hash binds bytes, not
approver identity. The leaves' `SKILL.md` own forms, options, budgets and
procedures; this doc keeps the boundaries and guards.

Across every family: never invent a listening verdict. Meters, ASR readback,
seeds and waveform/PCM hashes are evidence, not proof of hearing, pronunciation,
performance or a seamless loop; perceptual acceptance is human-reported.
Vocal-song generation and standalone audio visualization have no hands leaf: a
request for either is `no skill fits`, never routed to a core/external stand-in.

## Speech family

Three leaves under `audio-creator-pipeline/<verb>/speech/`, not a second menu
system. Profiles with ordinary conversational TTS use it for their own replies
only, never as a speech-asset bypass.

- `generate-speech`: one approved script. `voice` is `house` (the ordinary
  language fallback chain, including online Edge) or a qualified registered
  `<engine>:<voice>` ID; a local-only request names a qualified local voice,
  which never falls back. Style/seed the selected engine does not advertise
  are rejected, never silently dropped. `free` is a media-fee class, not
  unlimited takes: failed calls count, and packaging retries reuse raw audio.
- `edit-speech`: transforms existing audio into a new bundle; no new synthesis.
  A stale timing sidecar fails rather than being reused.
- `analyze-speech`: findings only, no deliverable file.

`speech-media.py` never installs an engine or downloads weights inside a job.
Subtitle times are estimated from ASR, not forced alignment. ASR is evidence,
not a verdict: coverage cannot excuse missing foreign words, and a spelling
variant is never a reason to re-roll. None of this verifies pronunciation,
emotion or voice likeness.

### Character voices and performance direction

AudioCreator — and only AudioCreator — gets `character_voices` and
`character_text_to_speech` from the engine-agnostic `tts/character-voice`
plugin. A named character asset is the opposite contract from ordinary speech:
the caller pins the sound, so nothing routes, nothing substitutes, and the tool
never touches `tts.fallback.chain` — reading it would smuggle language routing
into an explicit contract. Creator has no character tools.

- Voices are registered from the private character library by
  `characters sync`; AudioCreator never registers a voice.
- `character_voices` lists registered voices as qualified `<engine>:<voice-id>`
  (reference-free entries are filtered out: their timbre changes per run). The
  same ID is `generate-speech`'s `voice` value.
- A bare voice ID is rejected: the engine is half of the identity — the same
  reference renders audibly differently on the two engines.
- A refusal (unregistered voice, stopped engine, Irodori declining
  English-dominant text) is an error that names the engine and writes no file,
  never a hand-off. Never retry a refused character voice on the other engine.

Style control (emoji vocalisation, free-text `style`/`caption`, `seed`) belongs
only to this explicit contract. `character-voice` reads the provider's
advertised `style_features` and REFUSES any control the named engine doesn't
list; it never learns an engine name for this gating and never drops a control
silently — that would return a file that is not the requested take. The
fallback chain passes no style arguments and must not start doing so.

- **Emoji become performance** on an engine listing `emoji`: acted out, never
  read aloud, each adding audible duration. The character path parks emoji
  behind ASCII placeholders across Hermes' shared cleaner
  (`tools/tts_text_normalize.py`) and restores them. Never weaken that cleaner:
  everywhere else emoji are stripped, because an emoji reaching `qwen3-tts` or
  `edge` is read aloud as its name.
- **`seed`**: Irodori draws a fresh seed per request when left alone, so the
  tool always pins one and returns it; the same script and seed rebuild the same
  take while the engine's checkpoint is unchanged (a checkpoint change in
  `engines/` invalidates every earlier seed). Qwen3 exposes no seed. A seed
  rebuilds _that take_; it does not make a different line match an approved
  one. Verify reproduction on decoded SAMPLES, not container bytes — the Ogg
  carries a random bitstream serial.

Language routing of the fallback chain, engine installation and voice data
handling: [`ops/tts-engines.md`](../ops/tts-engines.md).

Character tools resolve on AudioCreator only because the toolset resolver memo
is keyed on profile scope in the hermes-agent checkout (a local patch); without
it a warm `tts` entry in another profile hides them. Registration-only tests and
direct CLI synthesis cannot detect that gateway-specific loss;
`test_audio_creator_routing.py` exercises the real resolver across scopes.

## SFX family

SFX is a separate four-leaf subject under `audio-creator-pipeline/<verb>/sfx/`,
not a music or mix family, and adds no profile, peer, gain automation or TTS.

- `create-sfx`: deterministic local kernels; the seed controls noise, not a
  model.
- `generate-sfx`: `local:stable-audio-3-medium` by default ($0, seeded) or an
  explicitly named `fal:elevenlabs-sfx-v2` (metered, no seed). Neither engine
  ever falls back to the other, automatically or silently. Local rejects
  fal-only controls rather than dropping them. fal needs the client's explicit
  current-work paid approval of prompt, seconds, loop, call cap and `max_usd`
  before any spend. Every attempt, failures included, counts against the call
  cap; the default cap is a proposal on either engine, never a spend grant.
- `edit-sfx` / `analyze-sfx`: always a new bundle or findings only; neither
  ever generates.

`sfx-media.py` publishes new bundles atomically and never replaces an existing
directory. Its PCM hashes are f32le decoded samples, not speech's mono s16le
convention. Silence/clipping fails; short SFX with no integrated LUFS is a
WARN, not a reason to re-roll. Peak, clipping, attack and boundary samples are
measurements, never proof of hearing or of a seamless loop.

The `plugins/audio_gen/sfx-gen` plugin registers only for audio-creator.
`sfx_generate` runs a bounded job whose frozen state fixes the engine, controls
and budget and counts an attempt before a paid submission; `resume` never
regenerates. An ambiguous fal submission stops for manual reconciliation. Paid
submission is one non-retrying HTTP POST — the SDK's automatic submit retries
could double-bill; only request-ID retrieval uses the SDK retry path.
`FAL_KEY` resolves from profile scope into an explicit SDK client, never a
process-env fallback.

Finished SFX reach video only as `create-ad` WAV cues ([`video.md`](./video.md)
"Ad family") or as Mix sources.

### Local Stable Audio 3 Medium runtime

Shared by SFX and music; install and refresh commands:
[`ops/audio-tooling.md`](../ops/audio-tooling.md) "Local Stable Audio 3 Medium
runtime". Installation is maintainer-only; jobs never install, download or
mutate the runtime, and there is never a second engine, install or daemon.

- **Headroom before quantization.** Upstream `sa3_mlx.save_wav` hard-clips
  float output at full scale and Medium routinely decodes past it, and
  `edit-music` cannot repair a clipped source. The adapter therefore applies
  one constant gain when the peak exceeds the ceiling — no limiter, no loudness
  normalization — and records `headroom` in `take.json`. An adapter edit changes
  the install fingerprint: activate it with `refresh`, never a reinstall.
- **One render, one subprocess** sharing the runtime lock (one
  install-or-render at a time); `HF_HUB_OFFLINE` prevents lazy downloads but is
  not a network-sandbox claim.
- **Job state** freezes payload/runtime identity at `start`; `resume` only
  re-validates the saved receipt. A running attempt with no bundle is `failed`
  once the lock is free and stays counted. Never bypass drift checks or rewrite
  existing receipts.
- **The stat fingerprint is inode + mtime_ns + size, never `st_dev`:** macOS
  renumbers it across reboots, and false drift would push jobs toward paid fal.
  Stat drift after a reboot with `check --full` clean means a new volatile
  field, not the weights. The fast check is a version-pin guarantee, not a
  tamper-proof sandbox.
- **Licensing:** upstream code is MIT; the Medium weights carry Stability AI's
  Community License plus Gemma terms. This install is a personal-evaluation
  acceptance — no commercial registration and no implied blanket commercial
  authorization. Never describe Medium as gated, blocked or "coming soon", and
  keep no alias to the old 401-gated `local:stable-audio`.

## Music family

Music is instrumental BGM or a short melodic opener/closer under
`audio-creator-pipeline/<verb>/music/` — not Song and not Mix. A full song with
lyrics/singing or standalone sound design is `no skill fits`, never
approximated by a music leaf; combining finished sources is "Mix family" below.
Music adds no profile, peer, secret, model download or launch service.

- `create-music`: an exact deterministic score in a closed synthetic-waveform
  palette, rendered locally at zero spend and zero network. A described
  real-world/sampled instrument routes to `generate-music`.
- `generate-music`: `local:stable-audio-3-medium` by default ($0, seeded) or an
  explicitly chosen `fal:stable-audio-3-medium` (metered; needs current-work
  approval and a dollar cap). Neither direction falls back.
- `edit-music`: one source into a new bundle; never resynthesis.
- `analyze-music`: estimates plus findings, no delivery; also serves any
  client-supplied song, including vocal music, but never lyric, singing, genre,
  mood or instrument verdicts.

Users need not author a score or prompt. Both creation leaves are TWO rounds,
unconditionally, in one resident work conversation: round A has no audio and
writes the exact artifact (`score.json` / `prompt-v<N>.txt`), which
`scripts/music_plan.py propose` freezes with reference hashes into
`proposal-v<N>/proposal.md` at zero spend. Only a second handoff with the EXACT
`approved_plan` + `approval_sha256` releases a render or `music_generate`; a
changed creative field needs a new proposal. Attempts never reset on resume or
corrective reapproval, and the frozen artifact is the one to use even when
packaging an older take.

The `plugins/audio_gen/music-gen` plugin registers only for audio-creator and
mirrors `sfx-gen`'s approval/state machinery (hash-bound manifest, frozen
settings, an attempt ledger counting failures, single non-retrying paid POSTs).
fal requires an explicitly approved `max_calls` and a `max_usd` covering it,
never an implicit budget. Instruments, genre and vocal absence stay unverified.
Finished music reaches video through `create-ad`'s WAV cues or Mix.

Front matter: music leaves are the tightest fit for the 4,000-character
discovery prefix ([`overview.md`](./overview.md) "The form"); test the actual
`_find_all_skills` names, not just the topology validator. Runtime write
protection checks literal operations/targets, not `mv` inside a job path; keep
the music proposal CLI's guard-plus-proposal regression for that case.

## Mix family

Mix places already-finished sources on one shared timeline under
`audio-creator-pipeline/<verb>/mix/`. It is not synthesis and not a music/SFX
family: no generation, loops, speed/pitch changes, EQ, reverb, source
separation or video assembly — a request needing those routes to the fitting
leaf first, and a music/SFX leaf is still not itself a mixer. Mix adds no
engine, plugin, toolset, secret, peer, daemon or profile and shares no runtime
with the Stable Audio install.

- `create-mix`: finished speech/sfx/music sources placed as cues with
  gain/fade/envelope automation into one master. Without an exact
  `arrangement`, AudioCreator authors relative placement from
  `direction`/`must_keep`/`note`. A supplied `arrangement` is preserved
  verbatim, never reinterpreted; an out-of-range or nonexistent-source control
  is a `Q<n>:`, never silently clamped. An optional `timing` file fixes named
  cues exactly, never adjusted behind approval.
- `edit-mix`: revises one existing bundle from its frozen `mix.json` and
  `sources/` — never re-uploaded or re-synthesized audio, never stem separation
  from the master. An audio-inert request is refused as a no-op revision.
- `analyze-mix`: findings on any finished mix file (plus recorded placement when
  its bundle is supplied and hash-matches); no delivery file, no fresh ASR.

`create-mix`/`edit-mix` are TWO rounds, unconditionally: round A runs `propose`
and returns only a zero-render `proposal-v<N>/proposal.md` + SHA-256; only the
matching `approved_plan` + `approval_sha256` releases the render. Any changed
source, placement, gain/fade/envelope, duration, `target_lufs` or
`true_peak_dbtp` needs a new proposal. `target_lufs` has no hidden default — an
explicit authored choice, `null` included.

Every source stays the original standalone file, frozen and hash-verified.
A source's own defect (e.g. prior clipping) is kept and reported, never
silently corrected, and a mix that keeps it still FAILs, as does whole-silence
delivery. Normalization is measured constant gain only, never loudnorm's
implicit dynamic-limiter fallback; infeasible loudness/peak targets FAIL.
Captions come only from an existing `.words.json` sidecar on a speech source,
timing-adjusted to the cue's placement — never a fresh ASR pass on the mixed
master. Determinism is scoped to same spec + frozen sources + helper version +
environment → byte-identical PCM. The family is `cost: free` throughout. Exact
schema: the leaf's `references/arrangement.md`.

**Video integration.** A finished sfx/speech/music WAV may feed `create-mix` as
a source, the same way a finished WAV may feed `create-ad` as a cue — separate
forms, never folded into one handoff, never a direct hands-to-hands call.
Ad/Tour opt in with `audio_workflow: mix`: the Assistant brokers a preliminary
timing proposal from the video leaf, then the Mix proposal/approval/render, then
the ordinary video plan/preview approval using the real master/receipt hashes.
An approved plan contains no dummy audio or placeholders; only the master
plays (kept footage audio is a conflict). Tour binds `mix-caption-N`
text/timing to the distinct Mix `captions.json`; never relax speech's
`words.json` hash check or rewrite its hash. Final decoded audio duration and
peak are measured again. MV/clip finishing is create-master's
([`video.md`](./video.md) "Master family"). The synthetic fixture
(`scripts/tests/fixtures/mix-video/example.py`) verifies wiring, not real
speech/ASR quality or a live conversation.
