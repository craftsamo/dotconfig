# Audio hands (audio-creator)

Speech, SFX, music and mix families. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Speech family

`audio-creator-pipeline/<verb>/speech/` contains three leaves, not a second
menu system. Its model/fallback/auxiliary pins mirror ImageCreator's; tools
are terminal/file/tts/sfx_gen/skills/memory, with no vision, generation-image/video,
outbound A2A or external skill library. The existing profile secret helper
already accepts this profile; a dedicated empty Keychain layer is not required.

- `generate-speech`: one approved UTF-8 script, up to 600 characters. `voice`
  is `house` or a qualified registered ID. House may use online Edge fallback;
  local-only requests choose a qualified local voice. Style/seed require the
  selected engine's advertised capabilities and are never silently dropped.
  Default one take plus one corrective, including failures; packaging retries
  reuse raw audio and do not spend a new take.
- `edit-speech`: approved-order concatenation, boundary-only silence trim,
  pitch-preserving speed, measured two-pass normalization, format conversion.
  No new synthesis. New bundle only, preserving originals; at most 64 inputs
  and 600 seconds. Valid unchanged sidecars reuse exact decoded-duration
  offsets; timing changes require fresh ASR. A stale matching sidecar fails.
- `analyze-speech`: input format, decode, loudness/peak/silence and optional
  script readback, returned as findings without a deliverable file.

The shared `speech-media.py` keeps WAV + `.words.json` + SRT + `.take.json`
together (48 kHz mono PCM master; optional Opus or MP3 derivative). It uses
the already-cached faster-whisper `base`, never a download or installation.
Caption times are estimated from ASR, not forced alignment. Exact normalized
text matches are PASS, near matches WARN, missing/mismatched speech FAIL;
coverage cannot excuse missing foreign words. None verifies pronunciation,
emotion or voice likeness. Returned tool identity/seed and decoded PCM hashes
are evidence, never a fabricated listening claim. ASR confidence is retained.

Live verification (2026-09-06): English house narration produced a 5.520 s
WAV/Opus pair with zero clipping and -15.52 LUFS. Japanese qualified-voice
renders with identical script/style/seed produced identical decoded PCM in
two distinct takes (6.680 s, -18.99 LUFS, zero clipping). Japanese house
also rendered successfully but retained an unresolved low-confidence ASR
substitution. The word/number spelling differences remained WARN, without
automatic corrective synthesis. The joined Japanese pair measured 13.560 s,
with the second timeline offset by 6.880 s, and normalized to -16.08 LUFS
(WAV) / -16.07 LUFS (Opus), -1 dBTP and zero clipping. Analysis returned
findings without an audio output.

Natural-language and Assistant-shaped Creator CLI requests each called the
configured audio-creator A2A peer exactly once. Receiver sessions executed
the edit, not Creator; both delivered unchanged-duration 6.680 s masters at
-16.18 LUFS and -1 dBTP, carrying readback warnings. An incomplete Assistant
brief returned a text Q1 with zero takes. These are CLI/two-client-shape
checks, not a native Telegram interaction test or a prolonged soak.
The caller-owned resident-session wrapper also ran analyze-speech against
the English Opus file, returned findings with zero takes, and was closed.
The gateway owns :9909 in the same process as the other peers; startup took
about 95 s to audio readiness and 133 s overall. Agent-card HTTP 200 and
listener ownership, not launchctl's return, prove readiness. A premature CLI
`Unknown toolsets: a2a` warning occurred while plugin discovery was pending;
actual A2A calls succeeded. Do not add a second gateway to work around it.

Final ownership cutover exposed a different upstream defect: after Creator
lost character-voice, its warm `tts` toolset memo hid AudioCreator's correctly
registered character tools. The local Hermes checkout at `4f0309e9cf` now
adds profile scope to `resolve_toolset`'s cache key; the real-registry
regression failed before the fix and passed afterwards in both warming
orders. Upstream's canonical toolsets test file passes (26 tests); dotconfig
also carries a real-resolver guard to catch loss of the fix during updates.
The fix lives in the hermes-agent checkout as `fix/toolset-profile-scope-memo`
merged into `local` — a runtime dependency of this migration, not a file here.
After restarting with that fix, a fresh Creator A2A catalog request exposed
character_voices on AudioCreator and returned both local engines and their
supported controls, with zero synthesis takes. Creator's character tools
remain disabled; no permission widening was needed.

Migration: speech's old voice card, assistant plan/QA contract and canonical
TTS special case are retired. Character-voice tools register only for
audio-creator; Creator retains generic TTS for conversational replies only.
The former AudioCraft/HeartMuLa/songsee technics and assistant plan/QA routes
are deliberately withdrawn without replacements, per the agreed scope.
Instrumental music generation is now served via audio-creator's
create-music/generate-music/edit-music/analyze-music (see "Music family"
below); vocal-song generation and standalone audio visualization remain
future families, not external-skill fallbacks. Existing audio may still be
supplied to a legacy assembly.

Recovery points: public tracked baseline `8b392d9` and private-overlay
baseline `2d12e8d`. Restore only task-owned configuration/routes from those
revisions if withdrawing this change; do not reset other work. Remove the
audio-creator peer/external-root/allowlist entry together and restart the
single gateway after restoring the old routing/plugin ownership. Keep all
audio, sessions, models and voice data. Existing ignored menu/hub state was
left intact; upstream seeded SKILL.md was retained as `SKILL.upstream.md`.
The existing broken private persona link was repaired by supplying its
missing private target; no personalized file was overwritten.

## SFX family

SFX is a separate subject under `audio-creator-pipeline/<verb>/sfx/`, not a
music or mix family. Creator reads its forms through the existing hands root;
there is no new profile, peer, external skill library or kanban contract.

- `create-sfx`: deterministic local click, beep, chime, whoosh, riser, pop,
  ui-tick or noise-burst. The seed controls noise, not a generative model;
  identical recipe/environment parameters reproduce decoded master PCM.
- `generate-sfx`: local `local:stable-audio-3-medium` by default (`engine`
  omitted) or explicitly chosen `fal:elevenlabs-sfx-v2`. Local takes a
  `seed` (default 0; attempt N uses `(base + N - 1) mod 2^32`, returned
  with the result) and rejects `loop`/`prompt_influence` outright rather
  than dropping them; fal supports `loop` and `prompt_influence` but has
  **no seed**. The 3 variants plus 1 corrective default (`max_calls` 4,
  hard cap 8, every attempt including failures counted) is a proposal on
  either engine, never itself a spend grant. fal additionally needs the
  client's explicit current-work approval of the prompt, duration, loop,
  call cap and USD estimate before any spend; local needs no
  `paid_approved`/`max_usd` and reports `$0` actual spend. Neither engine
  ever falls back to the other, automatically or silently.
- `edit-sfx`: trim, duration-changing pitch, reverse, pad both ends, fades,
  explicit true-peak gain and format conversion, always into a new bundle.
- `analyze-sfx`: native-format measurements and findings without a delivery.

`sfx-media.py` uses numpy and ffmpeg/ffprobe, with no ASR or model downloads.
It freezes a single regular local source (<=16 MiB, <=22 seconds), preserves
mono/stereo including anti-phase channels, and packages 48 kHz s16le WAV plus
`.take.json`. It records native input evidence separately from the resampled
master and lossy derivatives. PCM hashes specify f32le decoded samples at the
reported rate/channel count, not speech's mono s16le hash convention. Bundles
publish atomically without replacing an existing directory. Silence/clipping
fails; short-transient LUFS can be unavailable and remains WARN. Attack and
boundary deltas are measurements, not auditory quality or a verified loop.
Speech's helper and its timing-sidecar contract are unchanged.

The standalone `plugins/audio_gen/sfx-gen` plugin registers only for
audio-creator, using dedicated `sfx_gen` CLI/A2A toolsets. `sfx_engines` is a
free capability lookup; `sfx_generate` starts, resumes or advances a bounded
job. State freezes the engine/controls/budget and counts before submitting.
Request IDs survive disconnections; resume never generates another take.
An ambiguous submission requires manual reconciliation, while a confirmed
completed request's 400/422 rejection consumes an attempt and permits the
next approved corrective. The scoped `FAL_KEY` is supplied to an explicit
SDK client, never a global environment fallback. Paid submission uses one
non-retrying HTTP POST, since SDK 0.13.1 retries ambiguous transport failures;
only request-ID retrieval uses the SDK's retry path. The tool acknowledgment of
paid approval is an operating contract, not proof of caller identity.

### Local Stable Audio 3 Medium runtime

`hermes/scripts/stable_audio3.py` adopts a pinned checkout + weights + a
hash-locked Python 3.11 MLX venv under the gitignored
`hermes/local/stable-audio-3/`. Installation is maintainer-only —
`python hermes/scripts/stable_audio3.py install --accept-terms` — and jobs
never install, download or mutate the runtime; `check` / `check --full`
report readiness (`--full` re-hashes weights and re-collects the
dependency manifest; the fast check trusts stat fingerprints, which is a
version-pin guarantee, not a tamper-proof sandbox against a deliberately
forged venv). Code (commit `779434a908193105335fd8d833418603625b2859`) and
three weight files (HF revision `da6edc54ddba10bfd79a077102ded687f80e882b`,
5,179,055,990 bytes total) are pinned in `engines/stable-audio-3/pins.json`;
dependencies are hash-locked in `requirements.lock`. Each render is a
brand-new subprocess — no LaunchAgent, no resident port, no GPU-resident
process — that inherits the shared runtime lock (one install-or-render at
a time; the child keeps the lock across a parent death) and is killed by
process-group SIGKILL at a 180s timeout. `HF_HUB_OFFLINE` /
`TRANSFORMERS_OFFLINE` prevent lazy model downloads during render; they
are not a network-sandbox claim.

Job state (schema v2) freezes the payload/runtime identity at `start`;
`resume` never regenerates — it only re-validates the existing
`take-NN/raw.wav` + `take.json` + `inference.log` (the receipt: engine,
model commit/revision, runtime fingerprint, the exact request, and the raw
WAV's own hashes) against the frozen attempt. A running attempt with no
bundle yet reports `pending` while the runtime lock is busy; once the lock
is free with still no bundle, the attempt is marked `failed` and stays
counted — `next` may spend the remaining grant. Raw audio is 44.1 kHz
16-bit stereo PCM; `sfx-media.py track` repackages it into the usual
48 kHz WAV bundle, given the take's real `take.json` via `--take-file`
(never a fal `.tool.json`).

Licensing: the upstream Stable Audio 3 code is MIT. The optimized Medium weights on
Hugging Face download anonymously (no auth) at the pinned revision; the
weights carry Stability AI's Community License plus Gemma terms, and this
installation is a personal-evaluation acceptance — it does not perform
commercial registration and does not imply blanket commercial
authorization on its own (cite the primary license pages when that
matters). The older Stable Audio Open path's HTTP 401 gated-repo response
is retired history explaining why the runtime switched to Medium/MLX; it
is not the current engine's status, and Medium must never be described as
gated, blocked or "coming soon".

Benchmark (2026-09-08, M4 Max 48 GiB, macOS 26.5.2): a 5-second door-creak
prompt over 3 takes (seeds 42, 42, 43) returned 220,500 frames per raw
44.1 kHz WAV. The first fresh-process render took 5.21s wall /
3.95s CLI-internal; the next two fresh processes took 1.71s/1.46s and
1.72s/1.46s (OS caches were not flushed between runs). Peak process RSS
was 3.20 GB; OS peak footprint was about 4.67 GB; the MLX allocator's own
peak was 3.82 GiB (not the whole resident set). Repeating seed 42 produced
byte-identical raw PCM/WAV both times; seed 43 differed. No clipping;
measured true peak was -7.45 dBTP (seed 42) and -5.76 dBTP (seed 43).
Perceptual door-sound quality and loop behavior remain unverified — these
are technical fixtures, not a listening verdict. No paid fal trial has
been run against this engine.

Verification (2026-09-08): all four leaves are visible in the real CLI;
PluginManager discovers `audio_gen/sfx-gen` and resolves both tools through
the dedicated scoped toolset. The actual AudioCreator CLI ran analyze-sfx
on a 0.2s deterministic beep, returned zero clipping/-6 dBTP and preserved
the short-LUFS WARN without generating or spending. A real HyperFrames
0.8.30 six-second ad placed beep/chime cues at 1s/3s, measured -5.94 dBTP,
and retained digital silence between cues. Repeated local synths matched
WAV bytes. These are technical fixtures, not subjective listening or a
paid fal render. After a drained SIGUSR1 restart, one launchd-owned gateway
served :9909 again. A real Creator specialist inquiry used the configured
audio-creator A2A endpoint, executed analyze-sfx in the receiver, preserved
the measured WARN and closed its specialist conversation. It made no media
generation calls. This is one inquiry-path smoke test, not a sustained
two-client production soak. Full repository tests still have an unrelated
assistant runtime-skill-root validation failure; unowned directories were
not changed.

Medium follow-through (2026-09-08): both 0.5s and 21.5s bounds rendered through
the actual sfx_generate tool with no fal credential access; resume reused
the same files and kept calls at 1. The longer raw WAV contained one
full-scale sample, so track correctly retained FAIL even though resampling
removed that full-scale sample from the 48 kHz master. No normalization or
corrective generation was hidden in the test. A real AudioCreator CLI form
with omitted engine then generated one 5s Medium take (seed 42). Packaging
first hit the terminal guard on a command-substituted executable path;
the leaf commands now use a literal Python path, and resuming packaged the
existing WAV/receipt successfully with zero additional generations. The
48 kHz stereo master measured -7.45 dBTP, -25.11 LUFS and zero clipping.
These are technical checks; prompt fidelity and listening stay unverified.
After the normal drained gateway restart, a Creator inquiry reached the
configured audio-creator A2A receiver and called sfx_engines there. Its live
result reported local:stable-audio-3-medium ready/free with seed support and
no loop support, alongside the explicitly paid fal alternative. The inquiry
closed without media generation or paid calls.

VideoCreator's `create-ad` consumes the finished WAV or a client-approved JSON
cue list. Up to 16 distinct WAV assets each have exactly one placement;
multiple placements require distinct positive `data-track-index` values.
Unity gain and framework-owned timing remain unchanged. Multi-audio renders
measure the final decoded true peak, rejecting silent/undecodable/clipping
output without normalizing it. Missing integrated LUFS is a warning. Existing
single-audio plans and frozen hashes are not migrated. No tour, MV, clip-audio
replacement, music or mixing capability is implied by this receiving path.

## Music family

Music is a separate subject under `audio-creator-pipeline/<verb>/music/`,
scoped to instrumental BGM or a short melodic opener/closer (create/generate
at most 60s; edit/analyze accept up to 600s/128 MiB)
— a full song with lyrics/singing or standalone sound design is
`no skill fits`, never approximated by either music leaf. Combining
already-finished sources onto one timeline is the separate Mix family
below ("Mix family"), never a music leaf. Creator reads its forms
through the existing hands root; there is no new profile, peer, external
skill library or kanban contract.

- `create-music`: an exact deterministic score of five closed electronic
  waveforms (sine/triangle/pulse/fm-bell/noise), authored by AudioCreator
  from the client's direction and rendered locally at zero spend, zero
  network calls. `minimal-electronic`/`chiptune`/`ambient-synth` are starting
  styles, not a closed menu; custom direction must fit the five-waveform
  palette. A described real-world/sampled instrument routes to
  `generate-music` instead.
- `generate-music`: a compact text prompt sent to
  `local:stable-audio-3-medium` by default (`engine` omitted, $0 spend,
  seed-controlled) or an explicitly chosen `fal:stable-audio-3-medium`
  (metered, also seed-controlled — unlike SFX's fal endpoint, both music
  engines take a seed). Neither engine falls back to the other,
  automatically or silently; `music_engines` is a free capability lookup.
- `edit-music`: trim, repeat-to-length with a crossfaded loop seam,
  fade in/out, gain or two-pass LUFS normalization with a -1 dBTP ceiling on an existing music
  file, always into a new bundle; never resynthesis.
- `analyze-music`: local numpy-based tempo/beat/key/triad/structural-boundary
  estimates plus format/loudness/clipping findings, no delivery. Works
  standalone on any client-supplied song for arrangement/harmony-style
  analysis, not only this pipeline's own deliveries; never lyrics or
  vocal-performance analysis.

Both `create-music` and `generate-music` are TWO rounds, unconditionally:
both use one resident work conversation from proposal through approval.
round A (no `approved_plan`/`approval_sha256`) writes `form.json` +
`arrangement.md` + the exact artifact (`score.json` for create,
`prompt-v<N>.txt` for generate) and returns only a
`proposal-v<N>/proposal.md` + its
SHA-256, with zero spend. `scripts/music_plan.py propose` builds that
proposal from the resolved form/settings and the artifact's own hash;
its frozen `score.json` or `generation-prompt.txt` is the artifact to use,
including when packaging an older take after a correction. Only a second
handoff with that EXACT `approved_plan`+`approval_sha256`,
relayed by Creator in the same work conversation, releases a
`music-media.py create` render or a `music_generate` tool call. A
changed creative field needs a new proposal and a new approval, never a
generation against stale approval text; attempts never reset on resume
or a corrective reapproval.

The standalone `plugins/audio_gen/music-gen` plugin registers only for
audio-creator, using the dedicated `music_gen` CLI/A2A toolset —
`music_engines` and `music_generate` (`action: start | next | resume`).
Its approval/state/evidence machinery mirrors `sfx-gen`'s: a hash-bound
approved manifest, frozen job settings, an attempt ledger that counts
every call including failures, single non-retrying paid POSTs, and
`resume` that only re-validates a checkpointed receipt — it never
regenerates. Local default allowance is **2 variants + 1 corrective,
max 3, hard cap 8**; fal requires an explicit approved `max_calls` and a
`max_usd` covering it at the published per-audio estimate, never an
implicit default budget. Metadata cost stays `metered` (the leaf can
still spend on fal), but actual local spend is reported as `$0`.

`hermes/scripts/stable_audio3.py` gained a second entry point,
`render_music(payload, out, root=None)`, alongside the existing
`render()` used by SFX — same pinned Medium/MLX runtime, same shared
lock, same 180s subprocess timeout, same install/licensing terms (see
"Local Stable Audio 3 Medium runtime" above); it is not a second engine
or a second install. `music-media.py` (audio-creator-pipeline/scripts/)
owns `create`, `track`, `edit` and `analyze` for music the way
`sfx-media.py` does for SFX, with its own PCM hash convention and
freeze/bundle rules documented in that leaf's `SKILL.md`.

Vocal-song generation and standalone audio visualization remain
withdrawn without a hands replacement; a request for either is
`no skill fits`, never routed to a core/external route as a stand-in.
Maintainer integration validation (2026-09-08, M4 Max 48 GB, pinned Medium
MLX 8-step recipe): 5s / 30s / 60s music took 1.90s / 3.01s / 4.08s through
the real plugin, with exact 44.1 kHz frame counts. A second 5s run with seed
42 reproduced the decoded PCM hash. Four local inference attempts total,
no paid call. A 20s 96 BPM synthetic score also reproduced its PCM hash;
its 6s edited cue measured -24.00 LUFS, -17.01 dBTP and zero clipped samples.
Real create-ad freeze/snapshot/render on installed HyperFrames 0.8.31 placed
that cue at 0..6s in a 15s MP4: full decode passed, output measured -24.00
LUFS / -17.00 dBTP, waveform correlation >0.9998 on each channel. A prior
test preview correctly refused a runtime version change instead of bypassing
approval. These are local helper/plugin and rendering tests, not gateway/A2A
soak or perceptual listening. Fal live generation remains unverified.

## Mix family

Mix is a separate subject under `audio-creator-pipeline/<verb>/mix/`,
scoped to placing already-finished speech/sfx/music sources on one
shared timeline — never synthesis, generation, looping, EQ, reverb,
source separation or video assembly, all of which are `no skill fits`
for this leaf and route to the fitting leaf first. Creator reads its
forms through the existing hands root; there is no new profile, peer,
external skill library, plugin, toolset or kanban contract, and Mix
shares no runtime with SFX/Music's Stable Audio install (it calls no
model at all).

- `create-mix`: 1-16 standalone local sources (WAV/FLAC/Ogg/MP3/AIFF,
  each ≤128 MiB, ≤512 MiB combined, ≤600s decoded), placed as ≤32 cues
  on a timeline of 1-600s with gain/fade/piecewise-dB-envelope
  automation, rendered to one 48 kHz PCM master. AudioCreator authors
  relative cue placement from `direction`/`must_keep`/`note` when no
  exact `arrangement` is supplied — no user-written spec required; a
  supplied `arrangement` is preserved verbatim, never reinterpreted, and
  an out-of-range/nonexistent-source control is a `Q<n>:`, never
  silently clamped. An optional `timing` file constrains named cues'
  exact `start`/`source_start`/`duration`, never adjusted behind
  approval.
- `edit-mix`: revises one existing mix bundle from a plain-language
  `changes` request against its frozen `mix.json` and `sources/` — never
  re-uploaded/re-synthesized audio, never stem separation from the
  master. An audio-inert `changes` request (e.g. renaming only) is
  refused by the helper as a no-op revision.
- `analyze-mix`: format/duration/channels/peak/true-peak/clipping/
  integrated-LUFS measurements on any finished mix file, plus (when a
  previous bundle directory is supplied) the actual recorded cue/source
  placement from its `mix.json`; that source must hash-match the supplied
  bundle's master. Findings only, no delivery file or fresh ASR pass.

Both `create-mix` and `edit-mix` are TWO rounds, unconditionally, the
same shape as `create-music`/`generate-music`: round A (no
`approved_plan`/`approval_sha256`) writes `spec.json` + `description.md`
and runs `mix-media.py propose` (`--previous <bundle>` for `edit-mix`),
returning only a `proposal-v<N>/proposal.md` + its SHA-256, with zero
renders. Only a second handoff with that EXACT
`approved_plan`+`approval_sha256`, relayed by Creator in the same work
conversation, releases a `mix-media.py render` call. A changed creative
field (any source, cue placement, gain/fade/envelope, duration,
`target_lufs`, `true_peak_dbtp`) needs a new proposal, never a render
against stale approval text. `target_lufs` has no hidden default —
AudioCreator states it as an explicit authored choice (`null` is a
valid choice); `true_peak_dbtp` defaults to -1 unless direction calls
for otherwise. Every input file is hash-verified against its frozen
`sources/` copy before use, and an existing input defect (e.g. a
source's own clipping) is retained and reported, never silently
corrected — a mix that retains it still FAILs, as does whole-silence
delivery. Captions (`captions.json` + `mix_<slug>.srt`), when produced,
come only from an existing `.words.json` sidecar on a speech source,
timing-adjusted to that cue's placement — never a fresh ASR pass on the
mixed master; overlapping spoken cue intervals or a trim crossing a
word/caption boundary is refused, not silently trimmed. `mix-media.py`
also owns `analyze` and `verify` (re-validates a bundle for reuse
without rerendering). Determinism claims are scoped to the same spec +
frozen sources + helper version + environment producing byte-identical
PCM. This entire family is `cost: free` (no provider fee): it is
deterministic placement/gain/fade/sum on already-decoded PCM, not a
model call, so there is no attempt ledger or paid-approval gate to
enforce beyond the approval-hash check itself.

A finished sfx/speech/music WAV from its own leaf may feed `create-mix`
as one of its `sources`, the same way a finished sfx WAV may feed
`create-ad` as a distinct placed cue — the two are separate forms,
never folded into one handoff. Creator brokers a preliminary timing
proposal from create-ad/create-tour, the Mix proposal/approval/render,
then the video's formal approval using the real master/receipt hashes.
No placeholders in an approved plan and no direct hands-to-hands call.
With `audio_workflow: mix`, both video leaves place only the finished
master. Tour consumes separately verified Mix captions, never a speech
sidecar with its hash rewritten. Old no-Mix paths remain unchanged.

Normalization uses a measured scalar gain, not loudnorm's implicit dynamic
limiter fallback. Infeasible target/peak pairs fail; float-bus overrange
before an approved scalar reduction is warned, not confused with already
clipped source PCM. Stereo-to-mono arithmetic-mean cancellation is recorded
and warned. See the leaf's `references/arrangement.md` for the exact schema.

Verification: the reproducible automated fixture at
`scripts/tests/fixtures/mix-video/example.py` produces synthetic bed/SFX
and a speech-role test tone with explicitly synthetic caption evidence.
Both actual local HyperFrames renders passed: 15s portrait ad and 8s
landscape tour, full decode, matching audio duration and peak checks.
Tour proof frames show the caption inside its 2..3s interval and absent
before/after. This verifies wiring, not real speech/ASR quality or a live
Creator conversation. No paid generation or gateway restart was performed.
